"""Tests for attendance feature (P5, P6, P14, P15)."""

from datetime import UTC
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import core
from play_sessions.models import (
    AttendanceChange,
    AttendanceHint,
    PlayerRSVP,
    PlaySession,
    SessionAttendance,
)
from play_sessions.services_attendance import (
    active_characters,
    attendance_rows,
    save_attendance,
    set_player_rsvp,
    who_is_coming,
)
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def _make_club_and_session():
    club = Club.objects.create(name="Test Club", slug="test-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    player = Membership.objects.create(user=player_user, club=club)
    session = PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=timezone.datetime(2024, 6, 15, 18, 0, tzinfo=UTC),
        game_master=gm,
    )
    return club, gm, player, session


@pytest.mark.story("P5")
def test_active_characters_only_returns_active():
    club = Club.objects.create(name="Active Club", slug="active-club")
    user = User.objects.create_user(email="u@test.com", password="pass12345678")
    membership = Membership.objects.create(user=user, club=club)
    char1 = Character.objects.create(name="Active Char", club=club, owner=membership)
    Character.objects.create(name="Inactive Char", club=club, owner=membership)

    with patch("play_sessions.core.character_is_active") as mock_active:
        mock_active.side_effect = lambda c: c.pk == char1.pk
        result = active_characters(club)

    assert len(result) == 1
    assert result[0].pk == char1.pk


@pytest.mark.story("P5")
def test_who_is_coming_groups_members_by_answer():
    club, gm, player, session = _make_club_and_session()
    Character.objects.create(
        name="Yes Char", club=club, owner=player, level=3, char_class="Fighter"
    )
    Character.objects.create(
        name="Maybe Char", club=club, owner=player, level=2, char_class="Rogue"
    )
    Character.objects.create(name="No Char", club=club, owner=player, level=1, char_class="Wizard")

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    # One PlayerRSVP per member: the most recent answer wins.
    set_player_rsvp(session, player, PlayerRSVP.Answer.MAYBE, gm.user)

    data = who_is_coming(session)

    assert len(data["groups"]) == 1
    assert data["groups"][0][0] == "Maybe"
    assert data["groups"][0][1][0]["player_name"] == str(player.user)
    assert data["groups"][0][1][0]["character_names"] == "Maybe Char, No Char, Yes Char"

    assert data["unanswered"] == []


@pytest.mark.story("P5")
def test_who_is_coming_shows_active_characters_as_hint():
    club, gm, player, session = _make_club_and_session()
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    Character.objects.create(name="Fighter", club=club, owner=player)
    Character.objects.create(name="Wizard", club=club, owner=other)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    data = who_is_coming(session)

    assert data["groups"][0][0] == "Yes"
    assert data["groups"][0][1][0]["character_names"] == "Fighter"
    other_row = data["unanswered"][0]
    assert other_row["player_name"] == str(other_user)
    assert other_row["character_names"] == "Wizard"


@pytest.mark.story("P5")
def test_who_is_coming_unanswered_players():
    club, gm, player, session = _make_club_and_session()
    Character.objects.create(name="Answered Char", club=club, owner=player)
    _ = Character.objects.create(name="Unanswered Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    data = who_is_coming(session)

    # The member answered, so they are not unanswered even if a character lacks an RSVP.
    assert data["unanswered"] == []


@pytest.mark.story("P5")
def test_who_is_coming_member_with_no_rsvp_is_unanswered():
    club, gm, player, session = _make_club_and_session()
    _ = Character.objects.create(name="Char 1", club=club, owner=player, level=3)
    _ = Character.objects.create(name="Char 2", club=club, owner=player, level=2)

    # No RSVPs at all
    data = who_is_coming(session)

    assert len(data["unanswered"]) == 1
    assert data["unanswered"][0]["player_name"] == str(player.user)
    assert "Char 1" in data["unanswered"][0]["character_names"]
    assert "Char 2" in data["unanswered"][0]["character_names"]


@pytest.mark.story("P5")
def test_who_is_coming_inactive_characters_hidden():
    club, gm, player, session = _make_club_and_session()
    char1 = Character.objects.create(name="Active Char", club=club, owner=player)
    Character.objects.create(name="Inactive Char", club=club, owner=player)

    with patch("play_sessions.core.character_is_active") as mock_active:
        mock_active.side_effect = lambda c: c.pk == char1.pk
        from play_sessions.models import PlayerRSVP

        PlayerRSVP.objects.create(
            session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
        )
        data = who_is_coming(session)

    # Inactive char should not appear in any group
    assert len(data["groups"]) == 1
    assert data["groups"][0][0] == "Yes"
    assert data["groups"][0][1][0]["character_names"] == "Active Char"
    assert data["unanswered"] == []


@pytest.mark.story("P5")
def test_attendance_rows_starts_from_yes_members():
    club, gm, player, session = _make_club_and_session()
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    Character.objects.create(
        name="Yes Char", club=club, owner=player, level=3, char_class="Fighter"
    )
    Character.objects.create(name="Maybe Char", club=club, owner=other, level=2, char_class="Rogue")

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    PlayerRSVP.objects.create(
        session=session, member=other, answer=PlayerRSVP.Answer.MAYBE, answered_by=gm.user
    )

    rows = attendance_rows(session, club)

    # Only the yes member is on the page
    assert len(rows) == 1
    assert rows[0]["player_name"] == str(player.user)
    assert rows[0]["characters"][0]["character"].name == "Yes Char"
    # None ticked at first
    assert rows[0]["characters"][0]["checked"] is False
    assert rows[0]["answer"] == PlayerRSVP.Answer.YES
    assert rows[0]["answer_status"] == "success"

    # The maybe member's character is not offered
    assert all(cr["character"].name != "Maybe Char" for r in rows for cr in r["characters"])


@pytest.mark.story("P5")
def test_attendance_rows_prefers_existing_attendance():
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    SessionAttendance.objects.create(
        session=session, character=char, played=False, confirmed_by=gm.user
    )

    rows = attendance_rows(session, club)
    assert rows[0]["characters"][0]["checked"] is False


@pytest.mark.story("P5")
def test_attendance_rows_hint_pre_ticks_checkbox():
    """An AttendanceHint pre-ticks the box but writes no attendance row."""
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    AttendanceHint.objects.create(session=session, character=char)

    rows = attendance_rows(session, club)
    assert rows[0]["characters"][0]["checked"] is True
    # ...but no SessionAttendance row exists yet
    assert not session.attendance.exists()


@pytest.mark.story("P6")
def test_save_attendance_first_save_writes_all_no_changes():
    club, gm, player, session = _make_club_and_session()
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    char1 = Character.objects.create(name="Char 1", club=club, owner=player)
    char2 = Character.objects.create(name="Char 2", club=club, owner=other)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    PlayerRSVP.objects.create(
        session=session, member=other, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    # No existing attendance
    assert not session.attendance.exists()

    changed = save_attendance(session, {char1.pk}, gm.user, club)

    # Both in-scope characters get rows
    assert session.attendance.count() == 2
    att1 = session.attendance.get(character=char1)
    att2 = session.attendance.get(character=char2)
    assert att1.played is True
    assert att2.played is False

    # First save writes no AttendanceChange
    assert AttendanceChange.objects.count() == 0

    # Returns all written characters
    assert set(c.pk for c in changed) == {char1.pk, char2.pk}


@pytest.mark.story("P6")
def test_save_attendance_second_save_writes_changes():
    club, gm, player, session = _make_club_and_session()
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    char1 = Character.objects.create(name="Char 1", club=club, owner=player)
    char2 = Character.objects.create(name="Char 2", club=club, owner=other)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    PlayerRSVP.objects.create(
        session=session, member=other, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    # First save
    save_attendance(session, {char1.pk}, gm.user, club)

    # Second save: change char1 to false, add char2
    changed = save_attendance(session, {char2.pk}, gm.user, club)

    # Two AttendanceChanges: char1 (true -> false), char2 (false -> true)
    assert AttendanceChange.objects.count() == 2
    changes = AttendanceChange.objects.order_by("changed_at")
    char1_change = next(c for c in changes if c.character == char1)
    char2_change = next(c for c in changes if c.character == char2)
    assert char1_change.old_played is True
    assert char1_change.new_played is False
    assert char2_change.old_played is False
    assert char2_change.new_played is True

    # Returns both changed characters
    assert len(changed) == 2
    assert {c.pk for c in changed} == {char1.pk, char2.pk}


@pytest.mark.story("P6")
def test_save_attendance_added_member_character_writes_old_null():
    """A member added after the first save gets old_played=None for new rows."""
    club, gm, player, session = _make_club_and_session()
    char1 = Character.objects.create(name="Char 1", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    # First save with only char1
    save_attendance(session, {char1.pk}, gm.user, club)

    # Another member joins late and is added as attending
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    char2 = Character.objects.create(name="Char 2", club=club, owner=other)
    set_player_rsvp(session, other, PlayerRSVP.Answer.YES, gm.user)

    # Second save: add char2 (never had a row before)
    _ = save_attendance(session, {char1.pk, char2.pk}, gm.user, club)

    # AttendanceChange for char2 with old_played=None
    changes = AttendanceChange.objects.filter(character=char2)
    assert changes.count() == 1
    assert changes.first().old_played is None
    assert changes.first().new_played is True


@pytest.mark.story("P6")
def test_save_attendance_unchanged_rows_not_touched():
    club, gm, player, session = _make_club_and_session()
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    char1 = Character.objects.create(name="Char 1", club=club, owner=player)
    Character.objects.create(name="Char 2", club=club, owner=other)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    PlayerRSVP.objects.create(
        session=session, member=other, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    save_attendance(session, {char1.pk}, gm.user, club)
    save_attendance(session, {char1.pk}, gm.user, club)  # No changes

    assert AttendanceChange.objects.count() == 0


@pytest.mark.story("P6")
def test_save_attendance_inactive_character_not_offered():
    club, gm, player, session = _make_club_and_session()
    char1 = Character.objects.create(name="Active Char", club=club, owner=player)
    char2 = Character.objects.create(name="Inactive Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    with patch("play_sessions.core.character_is_active") as mock_active:
        mock_active.side_effect = lambda c: c.pk == char1.pk
        # Try to save with both IDs - inactive should be ignored
        save_attendance(session, {char1.pk, char2.pk}, gm.user, club)

    assert session.attendance.count() == 1
    assert session.attendance.first().character == char1


@pytest.mark.story("P6")
def test_save_attendance_ignores_non_yes_members():
    """Characters of members who did not answer yes are never written."""
    club, gm, player, session = _make_club_and_session()
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    char_yes = Character.objects.create(name="Yes Char", club=club, owner=player)
    char_no = Character.objects.create(name="No Char", club=club, owner=other)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    PlayerRSVP.objects.create(
        session=session, member=other, answer=PlayerRSVP.Answer.NO, answered_by=gm.user
    )

    save_attendance(session, {char_yes.pk, char_no.pk}, gm.user, club)

    assert session.attendance.count() == 1
    assert session.attendance.first().character == char_yes


@pytest.mark.story("P6")
def test_save_attendance_removes_hints_on_confirm():
    """Hints only pre-tick: confirming attendance deletes them."""
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    AttendanceHint.objects.create(session=session, character=char)
    assert AttendanceHint.objects.filter(session=session).count() == 1

    save_attendance(session, set(), gm.user, club)

    assert AttendanceHint.objects.filter(session=session).count() == 0
    att = session.attendance.get(character=char)
    assert att.played is False


@pytest.mark.story("P6")
def test_save_attendance_signal_sent_once_per_save():
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    calls = []

    def handler(sender, **kwargs):
        calls.append(kwargs)

    core.attendance_saved.connect(handler)
    try:
        save_attendance(session, {char.pk}, gm.user, club)  # First save: char played=True
        save_attendance(session, set(), gm.user, club)  # Second save: char played=False
    finally:
        core.attendance_saved.disconnect(handler)

    assert len(calls) == 2
    assert calls[0]["session"] == session
    assert calls[0]["by"] == gm.user
    assert len(calls[0]["characters"]) == 1
    assert len(calls[1]["characters"]) == 1
    assert calls[1]["characters"][0].pk == char.pk


@pytest.mark.story("P6")
def test_attendance_view_player_gets_403(client):
    club, gm, player, session = _make_club_and_session()
    client.force_login(player.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.story("P6")
def test_attendance_view_anonymous_redirects_to_login(client):
    club, gm, player, session = _make_club_and_session()
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.story("P6")
def test_attendance_view_gm_and_admin_allowed(client):
    club, gm, player, session = _make_club_and_session()
    admin_user = User.objects.create_user(email="admin@test.com", password="pass12345678")
    Membership.objects.create(user=admin_user, club=club, is_club_admin=True)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    for user in [gm.user, admin_user]:
        client.force_login(user)
        url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.story("P19")
@pytest.mark.parametrize("answer", [None, PlayerRSVP.Answer.MAYBE, PlayerRSVP.Answer.NO])
def test_attendance_post_adds_unanswered_maybe_no_member(client, answer):
    """Adding an unanswered, maybe or no member records a yes RSVP by the GM."""
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)
    if answer is not None:
        set_player_rsvp(session, player, answer, gm.user)

    assert not session.attendance.exists()

    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"add_member": player.pk})
    assert response.status_code == 302

    # The member is now recorded as attending (yes RSVP) by the GM
    rsvp = PlayerRSVP.objects.get(session=session, member=player)
    assert rsvp.answer == PlayerRSVP.Answer.YES
    assert rsvp.answered_by == gm.user

    # They appear on the attendance page with their character unticked
    response = client.get(url)
    assert response.status_code == 200
    rows = response.context["rows"]
    assert len(rows) == 1
    assert rows[0]["characters"][0]["character"] == char
    assert rows[0]["characters"][0]["checked"] is False


@pytest.mark.story("P6")
def test_attendance_post_saves_ticked_characters(client):
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {f"members-{player.pk}": [char.pk]})
    assert response.status_code == 302

    att = SessionAttendance.objects.get(session=session, character=char)
    assert att.played is True
    assert att.confirmed_by == gm.user
    assert AttendanceChange.objects.count() == 0  # first save


@pytest.mark.story("P6")
def test_attendance_post_second_save_writes_history(client):
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    client.post(url, {f"members-{player.pk}": [char.pk]})
    # Correct: played -> absent
    client.post(url, {})

    changes = AttendanceChange.objects.filter(character=char)
    assert changes.count() == 1
    assert changes.first().old_played is True
    assert changes.first().new_played is False


@pytest.mark.story("P6")
def test_bringing_view_creates_hint_only(client):
    """A player can hint they are bringing a character; no attendance row is written."""
    club, gm, player, session = _make_club_and_session()
    # Session already started
    session.starts_at = timezone.datetime(2020, 1, 1, 18, 0, tzinfo=UTC)
    session.save()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    client.force_login(player.user)
    url = reverse("play_sessions:bringing", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": char.pk})
    assert response.status_code == 200

    assert AttendanceHint.objects.filter(session=session, character=char).exists()
    # No SessionAttendance row is written
    assert not session.attendance.exists()

    # The hint pre-ticks the checkbox on the attendance page
    client.force_login(gm.user)
    attend_url = reverse(
        "play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    response = client.get(attend_url)
    rows = response.context["rows"]
    assert rows[0]["characters"][0]["checked"] is True


@pytest.mark.story("P6")
def test_bringing_view_removed_on_confirm(client):
    club, gm, player, session = _make_club_and_session()
    session.starts_at = timezone.datetime(2020, 1, 1, 18, 0, tzinfo=UTC)
    session.save()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )

    client.force_login(player.user)
    url = reverse("play_sessions:bringing", kwargs={"club_slug": club.slug, "pk": session.pk})
    client.post(url, {"character": char.pk})
    assert AttendanceHint.objects.filter(session=session).count() == 1

    # Confirming attendance removes the hint
    client.force_login(gm.user)
    attend_url = reverse(
        "play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    client.post(attend_url, {})
    assert AttendanceHint.objects.filter(session=session).count() == 0


@pytest.mark.story("P6")
def test_bringing_view_before_start_refused(client):
    club, gm, player, session = _make_club_and_session()
    # Session has not started yet
    session.starts_at = timezone.datetime(2030, 1, 1, 18, 0, tzinfo=UTC)
    session.save()
    char = Character.objects.create(name="Char", club=club, owner=player)

    client.force_login(player.user)
    url = reverse("play_sessions:bringing", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": char.pk})
    assert response.status_code == 400


@pytest.mark.story("P6")
def test_bringing_view_after_confirm_refused(client):
    club, gm, player, session = _make_club_and_session()
    session.starts_at = timezone.datetime(2020, 1, 1, 18, 0, tzinfo=UTC)
    session.save()
    char = Character.objects.create(name="Char", club=club, owner=player)

    PlayerRSVP.objects.create(
        session=session, member=player, answer=PlayerRSVP.Answer.YES, answered_by=gm.user
    )
    save_attendance(session, set(), gm.user, club)  # confirm

    client.force_login(player.user)
    url = reverse("play_sessions:bringing", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": char.pk})
    assert response.status_code == 400


@pytest.mark.story("P6")
def test_bringing_view_other_players_character_refused(client):
    club, gm, player, session = _make_club_and_session()
    session.starts_at = timezone.datetime(2020, 1, 1, 18, 0, tzinfo=UTC)
    session.save()
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    char = Character.objects.create(name="Char", club=club, owner=other)

    client.force_login(player.user)
    url = reverse("play_sessions:bringing", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": char.pk})
    assert response.status_code == 403


@pytest.mark.story("P19")
def test_add_member_menu_lists_not_yes_members_labelled(client):
    """The menu lists every non-yes member labelled with their answer."""
    club, gm, player, session = _make_club_and_session()
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    never_user = User.objects.create_user(email="never@test.com", password="pass12345678")
    never = Membership.objects.create(user=never_user, club=club)
    Character.objects.create(name="Char", club=club, owner=player)
    Character.objects.create(name="Other Char", club=club, owner=other)
    Character.objects.create(name="Never Char", club=club, owner=never)

    set_player_rsvp(session, player, PlayerRSVP.Answer.MAYBE, gm.user)
    set_player_rsvp(session, other, PlayerRSVP.Answer.NO, gm.user)

    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 200

    page = response.content.decode()
    assert "never answered" not in page
    assert "(maybe)" in page
    assert "(no)" in page
    assert "(no answer)" in page

    form = response.context["form"]
    queryset = form.fields["add_member"].queryset
    assert player in queryset
    assert other in queryset
    assert never in queryset
    assert gm in queryset

    labels = {m.pk: str(form.fields["add_member"].label_from_instance(m)) for m in queryset}
    assert "(maybe)" in labels[player.pk]
    assert "(no)" in labels[other.pk]
    assert "(no answer)" in labels[never.pk]
    assert "(no answer)" in labels[gm.pk]


@pytest.mark.story("P19")
def test_yes_member_never_offered_twice(client):
    """A yes member is not in the menu and a forged POST changes nothing."""
    club, gm, player, session = _make_club_and_session()
    Character.objects.create(name="Char", club=club, owner=player)
    set_player_rsvp(session, player, PlayerRSVP.Answer.YES, gm.user)

    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 200

    form = response.context["form"]
    assert player not in form.fields["add_member"].queryset
    page = response.content.decode()
    assert "never answered" not in page

    rsvp_count_before = PlayerRSVP.objects.count()
    response = client.post(url, {"add_member": player.pk})
    assert response.status_code == 302
    assert PlayerRSVP.objects.count() == rsvp_count_before
    assert not session.attendance.exists()

    response = client.get(url)
    assert player not in response.context["form"].fields["add_member"].queryset


@pytest.mark.story("P19")
def test_attendance_post_refuses_other_club_member(client):
    """A member of another club is refused."""
    club, gm, player, session = _make_club_and_session()
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    other_user = User.objects.create_user(email="otherclub@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=other_club)

    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"add_member": other.pk})
    assert response.status_code == 302
    assert not PlayerRSVP.objects.filter(session=session).exists()
    assert not session.attendance.exists()


@pytest.mark.story("P19")
def test_attendance_post_added_maybe_member_character_saves_played(client):
    """An added maybe member's ticked character saves as played=True."""
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)
    set_player_rsvp(session, player, PlayerRSVP.Answer.MAYBE, gm.user)

    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    client.post(url, {"add_member": player.pk})
    client.post(url, {f"members-{player.pk}": [char.pk]})

    att = SessionAttendance.objects.get(session=session, character=char)
    assert att.played is True
    assert att.confirmed_by == gm.user


@pytest.mark.story("P19")
def test_session_detail_shows_played_names(client):
    """The session page names played characters and no longer counts them."""
    club, gm, player, session = _make_club_and_session()
    played_char = Character.objects.create(name="Played Char", club=club, owner=player)
    Character.objects.create(name="Absent Char", club=club, owner=player)
    set_player_rsvp(session, player, PlayerRSVP.Answer.YES, gm.user)

    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    detail_url = reverse(
        "play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk}
    )

    # Before any save: no Played line
    response = client.get(detail_url)
    assert "Played:" not in response.content.decode()

    client.post(url, {f"members-{player.pk}": [played_char.pk]})

    response = client.get(detail_url)
    page = response.content.decode()
    assert "Played: Played Char" in page
    # played=False characters are not in the played list
    played_list = page.split("Played: ", 1)[1].split("<", 1)[0]
    assert played_list == "Played Char"
    assert "recorded for" not in page
