"""Tests for club time zone UI (P11)."""

import pytest
from django.conf import settings
from django.urls import reverse

from accounts.models import Club
from play_sessions import core
from play_sessions.models import PlaySession

pytestmark = [pytest.mark.django_db, pytest.mark.story("P11")]

CLUB_SETTINGS = "accounts:club_settings"
CLUB_NEW = "site_club_new"
CLUB_LIST = "site_clubs"


def _login(client, user):
    client.force_login(user)
    return client


def test_club_admin_get_settings(club_admin, login, club):
    """Club admin can open settings and sees warning and sorted zones."""
    c = _login(login(club_admin), club_admin)
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    r = c.get(url)
    assert r.status_code == 200
    body = r.content.decode()
    # Warning text present
    assert "Changing the time zone keeps the moment of every session" in body
    assert "19:00 can become 16:00" in body
    # Sorted option list (first few from zoneinfo)
    assert "America/New_York" in body
    assert "Europe/London" in body
    assert "UTC" in body


def test_superuser_get_settings(site_admin, login, club):
    """Superuser can open settings."""
    c = _login(login(site_admin), site_admin)
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    r = c.get(url)
    assert r.status_code == 200


def test_player_get_settings_403(player, login, club):
    """Player gets 403 on settings page."""
    c = _login(login(player), player)
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    assert c.get(url).status_code == 403


def test_player_post_settings_403(player, login, club):
    """Player gets 403 on POST to settings."""
    c = _login(login(player), player)
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    assert c.post(url, {"timezone": "America/New_York"}).status_code == 403


def test_anonymous_get_settings_redirects(club):
    """Anonymous user redirected to login."""
    from django.test import Client

    c = Client()
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    r = c.get(url)
    assert r.status_code == 302
    assert "/accounts/login/" in r.url


def test_club_admin_cannot_change_other_club(club_b_admin, login, club, other_club):
    """Club admin of club B cannot change club A."""
    c = _login(login(club_b_admin), club_b_admin)
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    # Should get 404 (middleware - not a member of club A)
    r = c.post(url, {"timezone": "America/New_York"})
    assert r.status_code == 404
    # Zone unchanged
    club.refresh_from_db()
    assert club.timezone == settings.TIME_ZONE


def test_post_valid_zone_saves(club_admin, login, club):
    """POST valid zone saves and redirects."""
    c = _login(login(club_admin), club_admin)
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    r = c.post(url, {"timezone": "America/New_York"})
    assert r.status_code == 302
    assert r.url == url
    club.refresh_from_db()
    assert club.timezone == "America/New_York"


def test_post_invalid_zone_refused(club_admin, login, club):
    """POST invalid zone gives 200 with error and zone unchanged."""
    c = _login(login(club_admin), club_admin)
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    original = club.timezone
    r = c.post(url, {"timezone": "Mars/Olympus"})
    assert r.status_code == 200
    body = r.content.decode()
    assert "Choose a time zone from the list" in body
    club.refresh_from_db()
    assert club.timezone == original


def test_post_blank_zone_refused(club_admin, login, club):
    """POST blank zone is refused."""
    c = _login(login(club_admin), club_admin)
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    original = club.timezone
    r = c.post(url, {"timezone": ""})
    assert r.status_code == 200
    body = r.content.decode()
    assert "This field is required" in body
    club.refresh_from_db()
    assert club.timezone == original


def test_zone_change_keeps_session_moment(club_admin, login, club):
    """Changing zone keeps session's UTC starts_at; local display changes."""
    c = _login(login(club_admin), club_admin)
    # Create a session with a specific UTC time
    import datetime

    utc_time = datetime.datetime(2024, 6, 15, 23, 0, tzinfo=datetime.UTC)
    session = PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=utc_time,
    )
    utc_before = session.starts_at

    # Change zone via form
    url = reverse(CLUB_SETTINGS, args=[club.slug])
    r = c.post(url, {"timezone": "America/Los_Angeles"})
    assert r.status_code == 302

    # Reload session - UTC should be same
    session.refresh_from_db()
    assert session.starts_at == utc_before

    # Local time should change (verify via to_club_local)
    club.refresh_from_db()
    local = core.to_club_local(club, session.starts_at)
    # 23:00 UTC = 16:00 PDT (America/Los_Angeles in June)
    assert local.hour == 16


def test_new_club_form_initial_zone(site_admin, login):
    """Site admin new club form has zone field with site default selected."""
    c = _login(login(site_admin), site_admin)
    url = reverse(CLUB_NEW)
    r = c.get(url)
    assert r.status_code == 200
    body = r.content.decode()
    # Check initial value equals settings.TIME_ZONE
    expected = f"selected>{settings.TIME_ZONE}</option"
    assert expected in body


def test_new_club_post_valid_zone_creates_club(site_admin, login):
    """POST with valid zone creates club with that zone."""
    c = _login(login(site_admin), site_admin)
    url = reverse(CLUB_NEW)
    r = c.post(
        url,
        {
            "name": "Zone Club",
            "slug": "",
            "admin_email": "zoneadmin@example.com",
            "admin_display_name": "Zone Admin",
            "timezone": "Europe/Paris",
        },
    )
    assert r.status_code == 200
    club = Club.objects.get(slug="zone-club")
    assert club.timezone == "Europe/Paris"


def test_new_club_post_bad_zone_no_club(site_admin, login):
    """POST with bad zone creates no club."""
    c = _login(login(site_admin), site_admin)
    url = reverse(CLUB_NEW)
    before = Club.objects.count()
    r = c.post(
        url,
        {
            "name": "Bad Zone Club",
            "slug": "",
            "admin_email": "badmin@example.com",
            "admin_display_name": "Bad Admin",
            "timezone": "Mars/Olympus",
        },
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert "Choose a time zone from the list" in body
    assert Club.objects.count() == before


def test_admin_nav_shows_club_settings_for_admin(club_admin, login, club):
    """Admin nav shows Club settings for club admin."""
    c = _login(login(club_admin), club_admin)
    url = reverse("club_home", args=[club.slug])
    r = c.get(url)
    assert r.status_code == 200
    body = r.content.decode()
    assert "Club settings" in body
    assert reverse(CLUB_SETTINGS, args=[club.slug]) in body


def test_admin_nav_hides_club_settings_for_player(player, login, club):
    """Admin nav does not show Club settings for player."""
    c = _login(login(player), player)
    url = reverse("club_home", args=[club.slug])
    r = c.get(url, follow=True)  # Player redirects to dashboard
    body = r.content.decode()
    # Player dashboard should not have Club settings
    assert "Club settings" not in body
