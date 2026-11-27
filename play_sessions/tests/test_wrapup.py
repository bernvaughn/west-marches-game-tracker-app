"""Tests for wrap-up feature (P21)."""

from datetime import UTC
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions.hooks_wrapup import wrapup_session
from play_sessions.models import PlaySession, SessionAttendance
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("P21")]


def _make_club_and_users():
    club = Club.objects.create(name="Wrap Club", slug="wrap-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    admin_user = User.objects.create_user(email="admin@test.com", password="pass12345678")
    admin = Membership.objects.create(user=admin_user, club=club, is_club_admin=True)
    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    player = Membership.objects.create(user=player_user, club=club)
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other = Membership.objects.create(user=other_user, club=club)
    return club, gm, admin, player, other


# Use a fixed "now" for all tests: 2024-06-02 (day after session ended)
FIXED_NOW = timezone.datetime(2024, 6, 2, 12, 0, tzinfo=UTC)


def _session_detail_url(club_slug, pk):
    return reverse("play_sessions:session_detail", kwargs={"club_slug": club_slug, "pk": pk})


def _club_home_url(club_slug):
    return reverse("club_home", kwargs={"club_slug": club_slug})


@pytest.fixture
def wrapup_club_and_session():
    club, gm, admin, player, other = _make_club_and_users()
    # Session ended within 14 days (ended 2024-06-01, now is 2024-06-02)
    session = PlaySession.objects.create(
        club=club,
        title="Ended Session",
        starts_at=timezone.datetime(2024, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    Character.objects.create(name="Hero", club=club, owner=player)
    Character.objects.create(name="Sidekick", club=club, owner=other)
    return club, gm, admin, player, other, session


def test_wrapup_session_with_ends_at(wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    result = wrapup_session(club, FIXED_NOW)
    assert result == session


def test_wrapup_session_without_ends_at(wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    session.ends_at = None
    session.save()
    result = wrapup_session(club, FIXED_NOW)
    assert result == session


def test_wrapup_session_14_day_edge():
    club = Club.objects.create(name="Edge Club", slug="edge-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    # Session ended on 2024-06-01 22:00
    session = PlaySession.objects.create(
        club=club,
        title="Edge Session",
        starts_at=timezone.datetime(2024, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    # 14 days later at 12:00 is still within 14 days (22:00 is the cutoff)
    now_within = timezone.datetime(2024, 6, 15, 12, 0, tzinfo=UTC)
    result = wrapup_session(club, now_within)
    assert result == session

    # 14 days later at 23:00 is past the cutoff
    now_past = timezone.datetime(2024, 6, 15, 23, 0, tzinfo=UTC)
    result = wrapup_session(club, now_past)
    assert result is None


def test_wrapup_session_future_session_excluded():
    club = Club.objects.create(name="Future Club", slug="future-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    PlaySession.objects.create(
        club=club,
        title="Future Session",
        starts_at=timezone.datetime(2030, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2030, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = wrapup_session(club, now)
    assert result is None


def test_wrapup_session_cancelled_excluded():
    club = Club.objects.create(name="Cancelled Club", slug="cancelled-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    PlaySession.objects.create(
        club=club,
        title="Cancelled Session",
        starts_at=timezone.datetime(2024, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
        cancelled=True,
    )
    now = timezone.datetime(2024, 6, 2, 12, 0, tzinfo=UTC)
    result = wrapup_session(club, now)
    assert result is None


def test_wrapup_session_older_when_newer_exists():
    club = Club.objects.create(name="Multi Club", slug="multi-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    # Older session
    PlaySession.objects.create(
        club=club,
        title="Old Session",
        starts_at=timezone.datetime(2024, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    # Newer session (ended later)
    new = PlaySession.objects.create(
        club=club,
        title="New Session",
        starts_at=timezone.datetime(2024, 6, 5, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 5, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    now = timezone.datetime(2024, 6, 6, 12, 0, tzinfo=UTC)
    result = wrapup_session(club, now)
    assert result == new


# Session page visibility tests


def test_wrapup_visible_to_gm(client, wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    assert response.status_code == 200
    assert b"Wrap up" in response.content


def test_wrapup_visible_to_club_admin(client, wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    client.force_login(admin.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    assert response.status_code == 200
    assert b"Wrap up" in response.content


def test_wrapup_not_visible_to_player(client, wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    client.force_login(player.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    assert response.status_code == 200
    assert b"Wrap up" not in response.content


def test_wrapup_not_visible_on_future_session(client):
    club = Club.objects.create(name="Future Club", slug="future-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    session = PlaySession.objects.create(
        club=club,
        title="Future Session",
        starts_at=timezone.datetime(2030, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2030, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    assert b"Wrap up" not in response.content


def test_wrapup_not_visible_on_cancelled_session(client):
    club = Club.objects.create(name="Cancelled Club", slug="cancelled-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    session = PlaySession.objects.create(
        club=club,
        title="Cancelled Session",
        starts_at=timezone.datetime(2024, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
        cancelled=True,
    )
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    assert b"Wrap up" not in response.content


def test_wrapup_not_visible_over_14_days(client):
    club = Club.objects.create(name="Old Club", slug="old-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    session = PlaySession.objects.create(
        club=club,
        title="Old Session",
        starts_at=timezone.datetime(2024, 5, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 5, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    assert b"Wrap up" not in response.content


def test_wrapup_not_visible_on_older_session_when_newer_exists(client):
    club = Club.objects.create(name="Multi Club", slug="multi-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    # Older session
    old = PlaySession.objects.create(
        club=club,
        title="Old Session",
        starts_at=timezone.datetime(2024, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    # Newer session (ended later)
    new = PlaySession.objects.create(
        club=club,
        title="New Session",
        starts_at=timezone.datetime(2024, 6, 5, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 5, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    client.force_login(gm.user)
    now = timezone.datetime(2024, 6, 6, 12, 0, tzinfo=UTC)
    with patch("django.utils.timezone.now", return_value=now):
        # On the older session page, wrapup should not show
        url = _session_detail_url(club.slug, old.pk)
        response = client.get(url)
        assert b"Wrap up" not in response.content
        # On the newer session page, wrapup should show
        url = _session_detail_url(club.slug, new.pk)
        response = client.get(url)
        assert b"Wrap up" in response.content


# Status tests


def test_wrapup_attendance_recap_not_done(client, wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    content = response.content.decode()
    assert "Not done" in content
    assert "Take attendance" in content
    assert "Write recap" in content


def test_wrapup_attendance_done(client, wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    char = Character.objects.get(name="Hero")
    SessionAttendance.objects.create(
        session=session, character=char, played=True, confirmed_by=gm.user
    )
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    content = response.content.decode()
    assert "Done" in content
    assert "Review attendance" in content


def test_wrapup_recap_done(client, wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    session.recap = "Great session!"
    session.save()
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    content = response.content.decode()
    assert "Done" in content
    assert "Edit recap" in content


# Links tests


def test_wrapup_links_present(client, wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _session_detail_url(club.slug, session.pk)
        response = client.get(url)
    content = response.content.decode()
    # Award loot link with session param
    assert f"?session={session.pk}" in content
    # Downtime points link
    assert "downtime:points_award" in content or "Downtime points" in content


# Session desk tests


def test_session_desk_award_loot_has_session_param(client, wrapup_club_and_session):
    club, gm, admin, player, other, session = wrapup_club_and_session
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _club_home_url(club.slug)
        response = client.get(url)
    content = response.content.decode()
    assert f"?session={session.pk}" in content


def test_session_desk_award_loot_plain_when_no_wrapup_session(client):
    club = Club.objects.create(name="No Wrap Club", slug="no-wrap-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _club_home_url(club.slug)
        response = client.get(url)
    content = response.content.decode()
    # Should not have session param
    assert "?session=" not in content
    assert "Award Loot to Party" in content


def test_session_desk_award_loot_plain_when_session_over_14_days(client):
    club = Club.objects.create(name="Old Club", slug="old-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    PlaySession.objects.create(
        club=club,
        title="Old Session",
        starts_at=timezone.datetime(2024, 5, 1, 18, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 5, 1, 22, 0, tzinfo=UTC),
        game_master=gm,
    )
    client.force_login(gm.user)
    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        url = _club_home_url(club.slug)
        response = client.get(url)
    content = response.content.decode()
    # Should not have session param
    assert "?session=" not in content
