"""Tests for the per-player RSVP merge (P16).

Covers: agreeing answers keep that answer, disagreeing answers use the most
recent by answered_at, answered_by/answered_at are copied from the chosen row,
the merge is idempotent, SessionAttendance is untouched, rows are unique per
(session, member), club scoping, and the report command prints the counts.
"""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions.models import (
    PlayerRSVP,
    PlaySession,
    SessionAttendance,
    SessionRSVP,
    merge_rsvps_to_player,
)
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("P16")]


def _merge_setup():
    """Club, one member with two characters, a session, and a second club."""
    club = Club.objects.create(name="Merge Club", slug="merge-club")
    owner_user = User.objects.create_user(email="owner@test.com", password="pass12345678")
    owner = Membership.objects.create(user=owner_user, club=club, is_game_master=True)
    char1 = Character.objects.create(name="Hero One", club=club, owner=owner)
    char2 = Character.objects.create(name="Hero Two", club=club, owner=owner)
    session = PlaySession.objects.create(
        club=club, title="Merge Session", starts_at=timezone.now(), game_master=owner
    )
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    return club, owner, char1, char2, session, other_club


def _make_rsvp(session, character, answer, by, when):
    # SessionRSVP.answered_at is auto_now_add, so set it after creation via
    # update() (which bypasses auto_now_add) to control the stored timestamp.
    rsvp = SessionRSVP.objects.create(
        session=session,
        character=character,
        answer=answer,
        answered_by=by,
    )
    SessionRSVP.objects.filter(pk=rsvp.pk).update(answered_at=when)
    rsvp.refresh_from_db()
    return rsvp


def test_merge_agreeing_answers_keeps_that_answer():
    club, owner, char1, char2, session, _other_club = _merge_setup()
    user = owner.user
    when = timezone.now() - timedelta(days=1)
    _make_rsvp(session, char1, SessionRSVP.Answer.YES, user, when)
    _make_rsvp(session, char2, SessionRSVP.Answer.YES, user, when)

    merged, mixed = merge_rsvps_to_player()

    assert merged == 1
    assert mixed == 0
    rsvp = PlayerRSVP.objects.get(session=session, member=owner)
    assert rsvp.answer == "yes"
    assert rsvp.answered_by == user
    assert rsvp.answered_at == when


def test_merge_disagreeing_uses_most_recent_by_answered_at():
    club, owner, char1, char2, session, _other_club = _merge_setup()
    user = owner.user
    early = timezone.now() - timedelta(days=2)
    late = timezone.now() - timedelta(days=1)
    _make_rsvp(session, char1, SessionRSVP.Answer.YES, user, early)
    _make_rsvp(session, char2, SessionRSVP.Answer.NO, user, late)

    merged, mixed = merge_rsvps_to_player()

    assert merged == 1
    assert mixed == 1
    rsvp = PlayerRSVP.objects.get(session=session, member=owner)
    assert rsvp.answer == "no"
    assert rsvp.answered_by == user
    assert rsvp.answered_at == late


def test_merge_copies_answered_by_and_answered_at_from_chosen_row():
    club, owner, char1, char2, session, _other_club = _merge_setup()
    user = owner.user
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    early = timezone.now() - timedelta(days=2)
    late = timezone.now() - timedelta(days=1)
    # The most recent row is owned by a different answered_by.
    _make_rsvp(session, char1, SessionRSVP.Answer.YES, user, early)
    _make_rsvp(session, char2, SessionRSVP.Answer.NO, other_user, late)

    merge_rsvps_to_player()

    rsvp = PlayerRSVP.objects.get(session=session, member=owner)
    assert rsvp.answer == "no"
    assert rsvp.answered_by == other_user
    assert rsvp.answered_at == late


def test_merge_is_idempotent():
    club, owner, char1, char2, session, _other_club = _merge_setup()
    user = owner.user
    when = timezone.now()
    _make_rsvp(session, char1, SessionRSVP.Answer.YES, user, when)
    _make_rsvp(session, char2, SessionRSVP.Answer.YES, user, when)

    merge_rsvps_to_player()
    first = PlayerRSVP.objects.get(session=session, member=owner)
    first_pk = first.pk

    # Second run creates nothing and changes nothing (agreeing -> mixed == 0).
    merged, mixed = merge_rsvps_to_player()
    assert merged == 0
    assert mixed == 0
    second = PlayerRSVP.objects.get(session=session, member=owner)
    assert second.pk == first_pk
    assert second.answer == "yes"
    assert PlayerRSVP.objects.filter(session=session, member=owner).count() == 1


def test_merge_attendance_untouched():
    club, owner, char1, _char2, session, _other_club = _merge_setup()
    user = owner.user
    when = timezone.now()
    _make_rsvp(session, char1, SessionRSVP.Answer.YES, user, when)
    attendance = SessionAttendance.objects.create(session=session, character=char1, played=True)

    merge_rsvps_to_player()

    attendance.refresh_from_db()
    assert attendance.played is True
    assert SessionAttendance.objects.filter(session=session, character=char1).count() == 1


def test_merge_unique_per_session_member():
    club, owner, char1, char2, session, _other_club = _merge_setup()
    user = owner.user
    when = timezone.now()
    _make_rsvp(session, char1, SessionRSVP.Answer.YES, user, when)
    _make_rsvp(session, char2, SessionRSVP.Answer.YES, user, when)

    merge_rsvps_to_player()

    # Re-running must not create a duplicate even though the merge writes the
    # same (session, member) key again via get_or_create.
    merge_rsvps_to_player()
    assert PlayerRSVP.objects.filter(session=session, member=owner).count() == 1

    # A different member on the same session gets its own row.
    other_user = User.objects.create_user(email="other2@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    char3 = Character.objects.create(name="Hero Three", club=club, owner=other)
    _make_rsvp(session, char3, SessionRSVP.Answer.NO, other_user, when)
    merge_rsvps_to_player()
    assert PlayerRSVP.objects.filter(session=session).count() == 2


def test_merge_is_club_scoped():
    club, owner, char1, char2, session, other_club = _merge_setup()
    user = owner.user
    when = timezone.now()
    _make_rsvp(session, char1, SessionRSVP.Answer.YES, user, when)

    other_user = User.objects.create_user(email="other3@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=other_club)
    other_session = PlaySession.objects.create(
        club=other_club, title="Other Session", starts_at=timezone.now(), game_master=other
    )
    other_char = Character.objects.create(name="Other Hero", club=other_club, owner=other)
    _make_rsvp(other_session, other_char, SessionRSVP.Answer.NO, other_user, when)

    merged, mixed = merge_rsvps_to_player()

    assert merged == 2
    assert PlayerRSVP.objects.for_club(club).count() == 1
    assert PlayerRSVP.objects.for_club(other_club).count() == 1


def test_report_command_prints_counts(capsys):
    club, owner, char1, char2, session, _other_club = _merge_setup()
    user = owner.user
    when = timezone.now()
    _make_rsvp(session, char1, SessionRSVP.Answer.YES, user, when)
    _make_rsvp(session, char2, SessionRSVP.Answer.NO, user, when)

    call_command("report_rsvp_merge")

    out = capsys.readouterr().out
    assert "Merged 1 player RSVPs" in out
    assert "1 players had mixed answers" in out
