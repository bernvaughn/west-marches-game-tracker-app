"""Tests for test email (E11)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from mail.models import ClubMailSettings, EmailMessage
from mail.sending import SendResult

pytestmark = [pytest.mark.django_db, pytest.mark.story("E11")]

RATELIMIT_CACHE_SETTINGS = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-email-rate-limit-tests",
    }
}


def _login(client, user):
    client.force_login(user)
    return client


def _clear_ratelimit(club_slug):
    """Clear rate limit cache for a club."""
    cache.delete(f"ratelimit:test_email:club:{club_slug}:3600")


def _mock_send_now_failure():
    """Patch send_now so the immediate send fails without touching the network.

    Keeps the message QUEUED and its payload intact, which is what the view
    does when the synchronous send fails.
    """
    return patch(
        "mail.views.test_email.send_now",
        return_value=SendResult(ok=False, provider_id="", error="network: test"),
    )


def test_test_email_get_requires_club_admin(club_admin, player, login, club):
    """Only club admins can access the test email view."""
    url = reverse("mail:test_email", args=[club.slug])

    # Club admin - should work
    c = _login(login(club_admin), club_admin)
    r = c.get(url)
    assert r.status_code == 200

    # Player - should get 403
    c = _login(login(player), player)
    r = c.get(url)
    assert r.status_code == 403


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_sends_to_admin(club_admin, login, club, settings):
    """Test email can be sent to the signed-in admin."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    with _mock_send_now_failure():
        r = c.post(url, {"recipient": club_admin.memberships.get(club=club).id})
    assert r.status_code == 200

    # Check email was queued with kind="test"
    msg = EmailMessage.objects.filter(club=club, kind="test").first()
    assert msg is not None
    assert msg.to_address == club_admin.email
    assert msg.subject.startswith("[Test]")
    assert "This is a test" in msg.payload.text
    assert msg.payload.reply_to == "club@test.com"


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_sends_to_other_admin(club_admin, game_master, login, club, settings):
    """Test email can be sent to another admin of the same club."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    # Make game_master an admin of this club
    gm_membership = game_master.memberships.get(club=club)
    gm_membership.is_club_admin = True
    gm_membership.save(update_fields=["is_club_admin"])
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    recipient_id = gm_membership.id
    with _mock_send_now_failure():
        r = c.post(url, {"recipient": recipient_id})
    assert r.status_code == 200

    msg = EmailMessage.objects.filter(club=club, kind="test").first()
    assert msg is not None
    assert msg.to_address == game_master.email


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_recipient_limited_to_admins(club_admin, player, login, club, settings):
    """Test email recipient must be an admin of the same club."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    # Try to send to a player (not admin)
    player_membership = player.memberships.get(club=club)
    r = c.post(url, {"recipient": player_membership.id})
    assert r.status_code == 400
    assert "Invalid recipient" in r.content.decode()

    # No email should be queued
    assert EmailMessage.objects.filter(club=club, kind="test").count() == 0


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_rate_limit(club_admin, login, club, settings):
    """Test email is rate limited to 5 per hour per club."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    recipient_id = club_admin.memberships.get(club=club).id

    # Send 5 emails - should succeed
    for i in range(5):
        with _mock_send_now_failure():
            r = c.post(url, {"recipient": recipient_id})
        assert r.status_code == 200, f"Request {i + 1} failed: {r.content.decode()}"

    # 6th email - should be rate limited (429)
    r = c.post(url, {"recipient": recipient_id})
    assert r.status_code == 429
    assert "Rate limit exceeded" in r.content.decode()


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_disabled_when_email_off(club_admin, login, club, settings):
    """Test email is disabled when email is off."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = False
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    recipient_id = club_admin.memberships.get(club=club).id
    r = c.post(url, {"recipient": recipient_id})
    assert r.status_code == 200
    body = r.content.decode()
    assert "Email is disabled" in body or "disabled" in body.lower()

    # A failed email should be logged (kind=test, status=failed)
    msg = EmailMessage.objects.filter(club=club, kind="test").first()
    assert msg is not None
    assert msg.status == EmailMessage.Status.FAILED
    assert "RESEND_API_KEY" in msg.last_error
    assert "site admin" in msg.last_error


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_log_shows_kind_test(club_admin, login, club, settings):
    """Test email log shows kind 'test'."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    recipient_id = club_admin.memberships.get(club=club).id
    with _mock_send_now_failure():
        r = c.post(url, {"recipient": recipient_id})
    assert r.status_code == 200

    msg = EmailMessage.objects.filter(club=club, kind="test").first()
    assert msg is not None
    assert msg.kind == "test"


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_page_shows_queued_status(club_admin, login, club, settings):
    """Page shows queued status for test email."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    recipient_id = club_admin.memberships.get(club=club).id
    with _mock_send_now_failure():
        r = c.post(url, {"recipient": recipient_id})
    assert r.status_code == 200
    body = r.content.decode()
    assert "Queued" in body or "queued" in body.lower()


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_page_shows_failed_with_reason(club_admin, login, club, settings):
    """Page shows failed status with plain reason from last_error."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = False  # Email off causes failed status
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    recipient_id = club_admin.memberships.get(club=club).id
    r = c.post(url, {"recipient": recipient_id})
    assert r.status_code == 200

    msg = EmailMessage.objects.filter(club=club, kind="test").first()
    assert msg is not None
    assert msg.status == EmailMessage.Status.FAILED
    assert "RESEND_API_KEY" in msg.last_error
    assert "site admin" in msg.last_error


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_htmx_returns_partial(club_admin, login, club, settings):
    """HTMX requests return the card partial."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    recipient_id = club_admin.memberships.get(club=club).id
    with _mock_send_now_failure():
        r = c.post(url, {"recipient": recipient_id}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Send a test email" in body
    assert "Recent test emails" in body


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_no_recipient_selected(club_admin, login, club, settings):
    """Error when no recipient is selected."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    r = c.post(url, {})  # No recipient
    assert r.status_code == 400
    assert "Select a recipient" in r.content.decode()


def _mock_resend_success(provider_id="resend_msg_123"):
    """Return an httpx.Client mock whose POST succeeds with provider_id."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": provider_id}
    mock_response.raise_for_status = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client_class = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    return mock_client_class


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_immediate_send_success(club_admin, login, club, settings):
    """Successful synchronous send marks the message SENT and shows provider ID."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    settings.EMAIL_FROM = "from@test.com"
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    mock_client_class = _mock_resend_success("resend_msg_123")

    with patch("httpx.Client", mock_client_class):
        c = _login(login(club_admin), club_admin)
        url = reverse("mail:test_email", args=[club.slug])
        recipient_id = club_admin.memberships.get(club=club).id
        r = c.post(url, {"recipient": recipient_id}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200

    msg = EmailMessage.objects.filter(club=club, kind="test").first()
    assert msg is not None
    assert msg.status == EmailMessage.Status.SENT
    assert msg.provider_id == "resend_msg_123"
    assert msg.sent_at is not None

    body = r.content.decode()
    assert "Sent" in body
    assert "resend_msg_123" in body


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_immediate_send_http_error(club_admin, login, club, settings):
    """Failed synchronous send keeps the message QUEUED and shows the error."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    settings.EMAIL_FROM = "from@test.com"
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_client.post.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=mock_response
    )
    mock_client_class = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    with patch("httpx.Client", mock_client_class):
        c = _login(login(club_admin), club_admin)
        url = reverse("mail:test_email", args=[club.slug])
        recipient_id = club_admin.memberships.get(club=club).id
        r = c.post(url, {"recipient": recipient_id}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200

    msg = EmailMessage.objects.filter(club=club, kind="test").first()
    assert msg is not None
    assert msg.status == EmailMessage.Status.QUEUED
    assert "http_401" in msg.last_error

    body = r.content.decode()
    assert "Failed" in body
    assert "http_401" in body


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_immediate_send_network_error(club_admin, login, club, settings):
    """Network error keeps the message QUEUED and shows a concrete reason."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = "resend_test_key"
    settings.EMAIL_FROM = "from@test.com"
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")
    mock_client_class = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    with patch("httpx.Client", mock_client_class):
        c = _login(login(club_admin), club_admin)
        url = reverse("mail:test_email", args=[club.slug])
        recipient_id = club_admin.memberships.get(club=club).id
        r = c.post(url, {"recipient": recipient_id}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200

    msg = EmailMessage.objects.filter(club=club, kind="test").first()
    assert msg is not None
    assert msg.status == EmailMessage.Status.QUEUED

    body = r.content.decode()
    assert "Failed" in body
    assert "network:" in body


@override_settings(CACHES=RATELIMIT_CACHE_SETTINGS)
def test_test_email_no_api_key_returns_400_no_row(club_admin, login, club, settings):
    """MAIL_ENABLED but no RESEND_API_KEY: POST is refused 400, no failed row."""
    from django.core.cache import caches

    caches["default"].clear()
    settings.MAIL_ENABLED = True
    settings.RESEND_API_KEY = ""
    ClubMailSettings.objects.create(club=club, contact_email="club@test.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:test_email", args=[club.slug])
    recipient_id = club_admin.memberships.get(club=club).id
    r = c.post(url, {"recipient": recipient_id}, HTTP_HX_REQUEST="true")
    assert r.status_code == 400
    body = r.content.decode()
    assert "No RESEND_API_KEY is set" in body

    # No failed row is written when a test email cannot be delivered.
    assert EmailMessage.objects.filter(club=club, kind="test").count() == 0
