"""Tests for bulk award prefill from session (P21)."""

import re
from datetime import UTC

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions.models import PlaySession, SessionAttendance
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("P21")]


@pytest.fixture
def _make_club_and_session_with_attendance():
    club = Club.objects.create(name="Prefill Club", slug="prefill-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    player = Membership.objects.create(user=player_user, club=club)
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)

    session = PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=timezone.datetime(2024, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )

    char1 = Character.objects.create(name="Played Char", club=club, owner=player)
    char2 = Character.objects.create(name="Did Not Play", club=club, owner=player)
    char3 = Character.objects.create(name="Other Played", club=club, owner=other)

    SessionAttendance.objects.create(
        session=session, character=char1, played=True, confirmed_by=gm.user
    )
    SessionAttendance.objects.create(
        session=session, character=char2, played=False, confirmed_by=gm.user
    )
    SessionAttendance.objects.create(
        session=session, character=char3, played=True, confirmed_by=gm.user
    )

    return club, gm, player, other, session, char1, char2, char3


def _get_checked_character_pks(content):
    """Extract character PKs that have checked checkboxes."""
    checked_checkboxes = re.findall(
        r'<input[^>]*name="characters"[^>]*value="(\d+)"[^>]*checked', content
    )
    return {int(pk) for pk in checked_checkboxes}


def test_prefill_ticks_only_played_true(client, _make_club_and_session_with_attendance):
    club, gm, player, other, session, char1, char2, char3 = _make_club_and_session_with_attendance
    client.force_login(gm.user)
    url = reverse("characters:bulk_award", args=[club.slug]) + f"?session={session.pk}"
    response = client.get(url)
    content = response.content.decode()
    checked_pks = _get_checked_character_pks(content)
    assert char1.pk in checked_pks, f"char1 ({char1.pk}) should be checked"
    assert char3.pk in checked_pks, f"char3 ({char3.pk}) should be checked"
    assert char2.pk not in checked_pks, f"char2 ({char2.pk}) should not be checked"


def test_prefill_note_is_session_title(client, _make_club_and_session_with_attendance):
    club, gm, player, other, session, char1, char2, char3 = _make_club_and_session_with_attendance
    client.force_login(gm.user)
    url = reverse("characters:bulk_award", args=[club.slug]) + f"?session={session.pk}"
    response = client.get(url)
    content = response.content.decode()
    assert "Test Session" in content
    # The note field should have the session title
    assert 'name="note"' in content
    assert "Test Session" in content.split('name="note"')[1][:200]


def test_prefill_date_is_session_date(client, _make_club_and_session_with_attendance):
    club, gm, player, other, session, char1, char2, char3 = _make_club_and_session_with_attendance
    client.force_login(gm.user)
    url = reverse("characters:bulk_award", args=[club.slug]) + f"?session={session.pk}"
    response = client.get(url)
    content = response.content.decode()
    # The date field should have the session date (2024-06-01)
    assert 'name="date"' in content
    assert "2024-06-01" in content.split('name="date"')[1][:200]


def test_prefill_without_session_param(client, _make_club_and_session_with_attendance):
    club, gm, player, other, session, char1, char2, char3 = _make_club_and_session_with_attendance
    client.force_login(gm.user)
    url = reverse("characters:bulk_award", args=[club.slug])
    response = client.get(url)
    content = response.content.decode()
    # No checkboxes should be ticked by default
    checked_pks = _get_checked_character_pks(content)
    assert len(checked_pks) == 0, f"No checkboxes should be checked, but found: {checked_pks}"


def test_prefill_bad_id_ignored(client, _make_club_and_session_with_attendance):
    club, gm, player, other, session, char1, char2, char3 = _make_club_and_session_with_attendance
    client.force_login(gm.user)
    # Non-numeric id
    url = reverse("characters:bulk_award", args=[club.slug]) + "?session=abc"
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should not have prefill
    checked_pks = _get_checked_character_pks(content)
    assert len(checked_pks) == 0

    # Non-existent id
    url = reverse("characters:bulk_award", args=[club.slug]) + "?session=999999"
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    checked_pks = _get_checked_character_pks(content)
    assert len(checked_pks) == 0


def test_prefill_foreign_session_ignored(client, _make_club_and_session_with_attendance):
    club, gm, player, other, session, char1, char2, char3 = _make_club_and_session_with_attendance
    # Create another club with a session
    other_club = Club.objects.create(name="Other Club", slug="other-club", timezone="UTC")
    other_gm_user = User.objects.create_user(email="othergm@test.com", password="pass12345678")
    other_gm = Membership.objects.create(user=other_gm_user, club=other_club, is_game_master=True)
    other_session = PlaySession.objects.create(
        club=other_club,
        title="Other Session",
        starts_at=timezone.datetime(2024, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 1, 22, 0, tzinfo=UTC),
        game_master=other_gm,
    )

    client.force_login(gm.user)
    # Use session from other club
    url = reverse("characters:bulk_award", args=[club.slug]) + f"?session={other_session.pk}"
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should not have prefill
    checked_pks = _get_checked_character_pks(content)
    assert len(checked_pks) == 0


def test_prefill_post_ignores_prefill(client, _make_club_and_session_with_attendance):
    club, gm, player, other, session, char1, char2, char3 = _make_club_and_session_with_attendance
    client.force_login(gm.user)
    url = reverse("characters:bulk_award", args=[club.slug]) + f"?session={session.pk}"
    # POST with only char2 selected (not the prefilled ones)
    data = {
        "characters": [str(char2.pk)],
        "note": "Custom note",
        "date": "2024-06-01",
        "coins_" + str(char2.pk): "100",
        f"items_{char2.pk}-TOTAL_FORMS": "0",
        f"items_{char2.pk}-INITIAL_FORMS": "0",
        f"items_{char2.pk}-MIN_NUM_FORMS": "0",
        f"items_{char2.pk}-MAX_NUM_FORMS": "500",
    }
    response = client.post(url, data)
    # Should redirect on success
    assert response.status_code == 302
    # Verify only char2 got the award
    from ledger.models import LedgerEntry

    entries = LedgerEntry.objects.filter(character__in=[char1, char2, char3], kind="award")
    assert entries.count() == 1
    assert entries.first().character == char2
