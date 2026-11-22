"""Tests for attendance feature (P5, P6)."""

from datetime import UTC
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import core
from play_sessions.models import AttendanceChange, PlaySession, SessionAttendance, SessionRSVP
from play_sessions.services_attendance import (
    active_characters,
    attendance_rows,
    save_attendance,
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
def test_who_is_coming_groups_by_answer():
    club, gm, player, session = _make_club_and_session()
    char1 = Character.objects.create(
        name="Yes Char", club=club, owner=player, level=3, char_class="Fighter"
    )
    char2 = Character.objects.create(
        name="Maybe Char", club=club, owner=player, level=2, char_class="Rogue"
    )
    char3 = Character.objects.create(
        name="No Char", club=club, owner=player, level=1, char_class="Wizard"
    )

    SessionRSVP.objects.create(
        session=session, character=char1, answer=SessionRSVP.Answer.YES, answered_by=gm.user
    )
    SessionRSVP.objects.create(
        session=session, character=char2, answer=SessionRSVP.Answer.MAYBE, answered_by=gm.user
    )
    SessionRSVP.objects.create(
        session=session, character=char3, answer=SessionRSVP.Answer.NO, answered_by=gm.user
    )

    data = who_is_coming(session)

    assert len(data["groups"]) == 3
    assert data["groups"][0][0] == "Yes"
    assert data["groups"][0][1][0]["character"].name == "Yes Char"
    assert data["groups"][0][1][0]["level"] == 3
    assert data["groups"][0][1][0]["char_class"] == "Fighter"
    assert data["groups"][0][1][0]["player_name"] == str(player.user)

    assert data["groups"][1][0] == "Maybe"
    assert data["groups"][2][0] == "No"

    assert data["unanswered"] == []


@pytest.mark.story("P5")
def test_who_is_coming_unanswered_players():
    club, gm, player, session = _make_club_and_session()
    # Player has one active character with RSVP, one without
    char1 = Character.objects.create(name="Answered Char", club=club, owner=player, level=3)
    _ = Character.objects.create(name="Unanswered Char", club=club, owner=player, level=2)

    SessionRSVP.objects.create(
        session=session, character=char1, answer=SessionRSVP.Answer.YES, answered_by=gm.user
    )

    data = who_is_coming(session)

    # Player has answered on char1, so should NOT be in unanswered
    assert data["unanswered"] == []


@pytest.mark.story("P5")
def test_who_is_coming_player_with_no_rsvp_is_unanswered():
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
    char2 = Character.objects.create(name="Inactive Char", club=club, owner=player)

    with patch("play_sessions.core.character_is_active") as mock_active:
        mock_active.side_effect = lambda c: c.pk == char1.pk
        # Give the active char an RSVP so player is not unanswered
        SessionRSVP.objects.create(
            session=session, character=char1, answer=SessionRSVP.Answer.YES, answered_by=gm.user
        )
        # Inactive char has RSVP but should not appear
        SessionRSVP.objects.create(
            session=session, character=char2, answer=SessionRSVP.Answer.YES, answered_by=gm.user
        )
        data = who_is_coming(session)

    # Inactive char should not appear in any group
    assert len(data["groups"]) == 1
    assert data["groups"][0][0] == "Yes"
    assert data["groups"][0][1][0]["character"].name == "Active Char"
    assert data["unanswered"] == []


@pytest.mark.story("P5")
def test_attendance_rows_starts_from_yes_rsvp():
    club, gm, player, session = _make_club_and_session()
    char_yes = Character.objects.create(
        name="Yes Char", club=club, owner=player, level=3, char_class="Fighter"
    )
    char_maybe = Character.objects.create(
        name="Maybe Char", club=club, owner=player, level=2, char_class="Rogue"
    )
    char_no = Character.objects.create(
        name="No Char", club=club, owner=player, level=1, char_class="Wizard"
    )
    _ = Character.objects.create(
        name="No RSVP Char", club=club, owner=player, level=4, char_class="Cleric"
    )

    SessionRSVP.objects.create(
        session=session, character=char_yes, answer=SessionRSVP.Answer.YES, answered_by=gm.user
    )
    SessionRSVP.objects.create(
        session=session, character=char_maybe, answer=SessionRSVP.Answer.MAYBE, answered_by=gm.user
    )
    SessionRSVP.objects.create(
        session=session, character=char_no, answer=SessionRSVP.Answer.NO, answered_by=gm.user
    )

    rows = attendance_rows(session, club)

    # Should be ordered: yes, maybe, no, none
    assert rows[0]["character"].name == "Yes Char"
    assert rows[0]["checked"] is True
    assert rows[1]["character"].name == "Maybe Char"
    assert rows[1]["checked"] is False
    assert rows[2]["character"].name == "No Char"
    assert rows[2]["checked"] is False
    assert rows[3]["character"].name == "No RSVP Char"
    assert rows[3]["checked"] is False

    # Check answer field
    assert rows[0]["answer"] == SessionRSVP.Answer.YES
    assert rows[1]["answer"] == SessionRSVP.Answer.MAYBE
    assert rows[2]["answer"] == SessionRSVP.Answer.NO
    assert rows[3]["answer"] is None


@pytest.mark.story("P5")
def test_attendance_rows_prefers_existing_attendance():
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    # RSVP says yes, but attendance says false
    SessionRSVP.objects.create(
        session=session, character=char, answer=SessionRSVP.Answer.YES, answered_by=gm.user
    )
    SessionAttendance.objects.create(
        session=session, character=char, played=False, confirmed_by=gm.user
    )

    rows = attendance_rows(session, club)
    assert rows[0]["checked"] is False


@pytest.mark.story("P6")
def test_save_attendance_first_save_writes_all_no_changes():
    club, gm, player, session = _make_club_and_session()
    char1 = Character.objects.create(name="Char 1", club=club, owner=player)
    char2 = Character.objects.create(name="Char 2", club=club, owner=player)

    # No existing attendance
    assert not session.attendance.exists()

    changed = save_attendance(session, {char1.pk}, gm.user, club)

    # Both characters get rows
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
    char1 = Character.objects.create(name="Char 1", club=club, owner=player)
    char2 = Character.objects.create(name="Char 2", club=club, owner=player)

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
def test_save_attendance_new_character_after_first_save_writes_old_null():
    club, gm, player, session = _make_club_and_session()
    char1 = Character.objects.create(name="Char 1", club=club, owner=player)

    # First save with only char1 (char2 doesn't exist yet)
    save_attendance(session, {char1.pk}, gm.user, club)

    # char2 created AFTER first save
    char2 = Character.objects.create(name="Char 2", club=club, owner=player)

    # Second save: add char2 (never had a row before because it didn't exist)
    _ = save_attendance(session, {char1.pk, char2.pk}, gm.user, club)

    # AttendanceChange for char2 with old_played=None
    changes = AttendanceChange.objects.filter(character=char2)
    assert changes.count() == 1
    assert changes.first().old_played is None
    assert changes.first().new_played is True


@pytest.mark.story("P6")
def test_save_attendance_unchanged_rows_not_touched():
    club, gm, player, session = _make_club_and_session()
    char1 = Character.objects.create(name="Char 1", club=club, owner=player)
    _ = Character.objects.create(name="Char 2", club=club, owner=player)

    save_attendance(session, {char1.pk}, gm.user, club)
    save_attendance(session, {char1.pk}, gm.user, club)  # No changes

    assert AttendanceChange.objects.count() == 0


@pytest.mark.story("P6")
def test_save_attendance_inactive_character_not_offered():
    club, gm, player, session = _make_club_and_session()
    char1 = Character.objects.create(name="Active Char", club=club, owner=player)
    char2 = Character.objects.create(name="Inactive Char", club=club, owner=player)

    with patch("play_sessions.core.character_is_active") as mock_active:
        mock_active.side_effect = lambda c: c.pk == char1.pk
        # Try to save with both IDs - inactive should be ignored
        save_attendance(session, {char1.pk, char2.pk}, gm.user, club)

    assert session.attendance.count() == 1
    assert session.attendance.first().character == char1


@pytest.mark.story("P6")
def test_save_attendance_signal_sent_once_per_save():
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    calls = []

    def handler(sender, **kwargs):
        calls.append(kwargs)

    core.attendance_saved.connect(handler)
    try:
        save_attendance(session, {char.pk}, gm.user, club)  # First save: char played=True
        save_attendance(session, set(), gm.user, club)  # Second save: char played=False (changed!)
    finally:
        core.attendance_saved.disconnect(handler)

    assert len(calls) == 2
    # First save
    assert calls[0]["session"] == session
    assert calls[0]["by"] == gm.user
    assert len(calls[0]["characters"]) == 1
    # Second save (char changed from True to False)
    assert len(calls[1]["characters"]) == 1
    assert calls[1]["characters"][0].pk == char.pk


@pytest.mark.story("P5")
def test_rsvp_for_view_gm_can_answer_for_anyone(client):
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Player's Char", club=club, owner=player)

    client.force_login(gm.user)
    url = reverse("play_sessions:rsvp_for", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": char.pk, "answer": SessionRSVP.Answer.YES})

    assert response.status_code == 302
    rsvp = SessionRSVP.objects.get(session=session, character=char)
    assert rsvp.answer == SessionRSVP.Answer.YES
    assert rsvp.answered_by == gm.user


@pytest.mark.story("P5")
def test_rsvp_for_view_works_after_start_time(client):
    """GM can answer after the session start time (no lock for GM/admin)."""
    club, gm, player, session = _make_club_and_session()
    # Session in the past
    session.starts_at = timezone.datetime(2020, 1, 1, 18, 0, tzinfo=UTC)
    session.save()

    char = Character.objects.create(name="Char", club=club, owner=player)

    client.force_login(gm.user)
    url = reverse("play_sessions:rsvp_for", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": char.pk, "answer": SessionRSVP.Answer.YES})

    assert response.status_code == 302
    assert SessionRSVP.objects.filter(session=session, character=char).exists()


@pytest.mark.story("P5")
def test_rsvp_for_view_changes_existing_answer_no_second_row(client):
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    # First RSVP
    SessionRSVP.objects.create(
        session=session, character=char, answer=SessionRSVP.Answer.YES, answered_by=player.user
    )

    client.force_login(gm.user)
    url = reverse("play_sessions:rsvp_for", kwargs={"club_slug": club.slug, "pk": session.pk})
    client.post(url, {"character": char.pk, "answer": SessionRSVP.Answer.NO})

    assert SessionRSVP.objects.filter(session=session, character=char).count() == 1
    rsvp = SessionRSVP.objects.get(session=session, character=char)
    assert rsvp.answer == SessionRSVP.Answer.NO
    assert rsvp.answered_by == gm.user


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


@pytest.mark.story("P5")
def test_rsvp_for_view_player_gets_403(client):
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    client.force_login(player.user)
    url = reverse("play_sessions:rsvp_for", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": char.pk, "answer": SessionRSVP.Answer.YES})
    assert response.status_code == 403


@pytest.mark.story("P5")
def test_rsvp_for_view_anonymous_redirects_to_login(client):
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    url = reverse("play_sessions:rsvp_for", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": char.pk, "answer": SessionRSVP.Answer.YES})
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.story("P6")
def test_attendance_view_gm_and_admin_allowed(client):
    club, gm, player, session = _make_club_and_session()
    admin_user = User.objects.create_user(email="admin@test.com", password="pass12345678")
    Membership.objects.create(user=admin_user, club=club, is_club_admin=True)

    for user in [gm.user, admin_user]:
        client.force_login(user)
        url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.story("P5")
def test_rsvp_for_view_gm_and_admin_allowed(client):
    club, gm, player, session = _make_club_and_session()
    admin_user = User.objects.create_user(email="admin@test.com", password="pass12345678")
    Membership.objects.create(user=admin_user, club=club, is_club_admin=True)
    char = Character.objects.create(name="Char", club=club, owner=player)

    for user in [gm.user, admin_user]:
        client.force_login(user)
        url = reverse("play_sessions:rsvp_for", kwargs={"club_slug": club.slug, "pk": session.pk})
        response = client.post(url, {"character": char.pk, "answer": SessionRSVP.Answer.YES})
        assert response.status_code == 302


@pytest.mark.story("P5")
def test_post_inactive_or_other_club_character_refused(client):
    club, gm, player, session = _make_club_and_session()
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other_membership = Membership.objects.create(user=other_user, club=other_club)
    other_char = Character.objects.create(
        name="Other Club Char", club=other_club, owner=other_membership
    )

    client.force_login(gm.user)
    url = reverse("play_sessions:rsvp_for", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"character": other_char.pk, "answer": SessionRSVP.Answer.YES})

    # Should not create RSVP for other club character
    assert not SessionRSVP.objects.filter(session=session, character=other_char).exists()
    assert response.status_code == 302  # Redirects with error message


@pytest.mark.story("P6")
def test_attendance_post_inactive_character_ignored(client):
    club, gm, player, session = _make_club_and_session()
    char = Character.objects.create(name="Char", club=club, owner=player)

    with patch("play_sessions.core.character_is_active", return_value=False):
        client.force_login(gm.user)
        url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
        client.post(url, {"characters": [char.pk]})

    # Should not create attendance for inactive character
    assert not SessionAttendance.objects.filter(session=session, character=char).exists()


@pytest.mark.story("P5")
def test_no_gm_notes_in_section_html(client):
    club, gm, player, session = _make_club_and_session()
    session.gm_notes = "Secret GM notes"
    session.save()

    client.force_login(player.user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert b"Secret GM notes" not in response.content


@pytest.mark.story("P6")
def test_attendance_history_time_in_club_zone(client):
    club, gm, player, session = _make_club_and_session()
    club.timezone = "Asia/Tokyo"
    club.save()
    char = Character.objects.create(name="Char", club=club, owner=player)
    fixed = timezone.datetime(2024, 6, 15, 20, 30, tzinfo=UTC)
    with patch("django.utils.timezone.now", return_value=fixed):
        AttendanceChange.objects.create(
            session=session, character=char, old_played=False, new_played=True, changed_by=gm.user
        )
    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    html = client.get(url).content.decode()
    # 20:30 UTC is 05:30 the next day in Tokyo.
    assert "Jun 16, 2024 05:30" in html
    assert "Jun 15, 2024 20:30" not in html


@pytest.mark.story("P6")
def test_attendance_badge_status_matches_answer(client):
    club, gm, player, session = _make_club_and_session()
    for name, answer in [
        ("Yes Char", SessionRSVP.Answer.YES),
        ("Maybe Char", SessionRSVP.Answer.MAYBE),
        ("No Char", SessionRSVP.Answer.NO),
    ]:
        char = Character.objects.create(name=name, club=club, owner=player)
        SessionRSVP.objects.create(
            session=session, character=char, answer=answer, answered_by=gm.user
        )
    client.force_login(gm.user)
    url = reverse("play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    rows = {r["character"].name: r for r in response.context["rows"]}
    assert rows["Yes Char"]["answer_status"] == "success"
    assert rows["Maybe Char"]["answer_status"] == "warning"
    assert rows["No Char"]["answer_status"] == "danger"
    html = response.content.decode()
    assert "wm-badge--warning" in html
    assert "wm-badge--danger" in html
