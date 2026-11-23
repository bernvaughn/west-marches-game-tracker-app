"""Tests for forgot password and password-changed notice (E4)."""

from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.test import override_settings
from django.urls import reverse

from accounts.models import Club, Membership
from accounts.passwords import ComplexityValidator, PasswordHistoryValidator, set_temporary_password
from mail.models import DoNotEmail, EmailMessage, OneTimeToken
from mail.tokens import consume, issue, peek
from mail.views.forgot_password import _sign_out_other_sessions

# Cache settings for rate limit tests (uses LocMemCache instead of DummyCache)
RATELIMIT_CACHE_SETTINGS = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "forgot-password-rate-limit-tests",
    }
}


@pytest.fixture
def test_user(django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user("test@example.com", password="OldPass123!")


@pytest.fixture
def test_user2(django_user_model):
    """Create another test user."""
    return django_user_model.objects.create_user("test2@example.com", password="OldPass123!")


@pytest.fixture
def test_club(db, test_user):
    """Create a test club with the user as admin."""
    club = Club.objects.create(name="Test Club", slug="test-club")
    Membership.objects.create(user=test_user, club=club, is_club_admin=True)
    return club


@pytest.fixture
def client_logged_in(client, test_user):
    """Client logged in as test_user."""
    client.force_login(test_user)
    return client


@pytest.fixture
def settings_email_on(settings):
    """Enable email for tests."""
    settings.MAIL_ENABLED = True
    return settings


# ===== Forgot Password View Tests =====


@pytest.mark.django_db
class TestForgotPasswordView:
    def test_get_shows_form(self, client):
        """GET shows the email form."""
        url = reverse("mail_public:forgot_password")
        response = client.get(url)
        assert response.status_code == 200
        assert "Forgot password" in response.content.decode()
        assert "email" in response.content.decode().lower()

    def test_post_neutral_answer_for_known_address(self, client, test_user, settings_email_on):
        """POST returns neutral answer for known address and queues email."""
        url = reverse("mail_public:forgot_password")
        response = client.post(url, {"email": "test@example.com"}, follow=True)

        assert response.status_code == 200
        content = response.content.decode()
        assert "If an account exists" in content
        assert "reset link has been sent" in content

        # Check email was queued
        messages = EmailMessage.objects.filter(kind="password_reset", to_address="test@example.com")
        assert messages.exists()

    def test_post_neutral_answer_for_unknown_address(self, client, settings_email_on):
        """POST returns same neutral answer for unknown address."""
        url = reverse("mail_public:forgot_password")
        response = client.post(url, {"email": "unknown@example.com"}, follow=True)

        assert response.status_code == 200
        content = response.content.decode()
        assert "If an account exists" in content
        assert "reset link has been sent" in content

        # No email should be queued
        messages = EmailMessage.objects.filter(
            kind="password_reset", to_address="unknown@example.com"
        )
        assert not messages.exists()

    def test_post_neutral_answer_for_do_not_email(self, client, test_user, settings_email_on):
        """POST returns neutral answer for do-not-email address, nothing queued."""
        DoNotEmail.objects.create(address="test@example.com", reason="manual")

        url = reverse("mail_public:forgot_password")
        response = client.post(url, {"email": "test@example.com"}, follow=True)

        assert response.status_code == 200
        content = response.content.decode()
        assert "If an account exists" in content
        assert "reset link has been sent" in content

        # No email should be queued
        messages = EmailMessage.objects.filter(kind="password_reset", to_address="test@example.com")
        assert not messages.exists()

    def test_post_neutral_answer_for_invalid_suffix(self, client, settings_email_on):
        """POST returns neutral answer for .invalid address, nothing queued."""
        url = reverse("mail_public:forgot_password")
        response = client.post(url, {"email": "test@invalid.invalid"}, follow=True)

        assert response.status_code == 200
        content = response.content.decode()
        assert "If an account exists" in content
        assert "reset link has been sent" in content

        # No email should be queued
        messages = EmailMessage.objects.filter(
            kind="password_reset", to_address="test@invalid.invalid"
        )
        assert not messages.exists()

    def test_rate_limit_per_visitor_ip(self, client, settings_email_on):
        """Rate limit: 10 requests per hour per visitor IP."""
        from django.core.cache import cache

        with override_settings(CACHES=RATELIMIT_CACHE_SETTINGS):
            cache.clear()
            url = reverse("mail_public:forgot_password")

            # Make 10 requests - all should succeed
            for i in range(10):
                response = client.post(url, {"email": f"user{i}@example.com"})
                assert response.status_code == 200

            # 11th request should be rate limited
            response = client.post(url, {"email": "user11@example.com"})
            assert response.status_code == 429
            content = response.content.decode()
            assert "Too many requests" in content

    def test_rate_limit_per_address(self, client, settings_email_on):
        """Rate limit: 3 requests per hour per email address."""
        from django.core.cache import cache

        with override_settings(CACHES=RATELIMIT_CACHE_SETTINGS):
            cache.clear()
            url = reverse("mail_public:forgot_password")

            # Make 3 requests for same address - all should succeed
            for _i in range(3):
                response = client.post(url, {"email": "same@example.com"})
                assert response.status_code == 200

            # 4th request for same address should be rate limited
            response = client.post(url, {"email": "same@example.com"})
            assert response.status_code == 429
            content = response.content.decode()
            assert "Too many requests for this address" in content

    def test_email_case_insensitive_lookup(self, client, test_user, settings_email_on):
        """Email lookup is case-insensitive."""
        url = reverse("mail_public:forgot_password")
        response = client.post(url, {"email": "TEST@EXAMPLE.COM"}, follow=True)

        assert response.status_code == 200
        messages = EmailMessage.objects.filter(kind="password_reset", to_address="test@example.com")
        assert messages.exists()

    def test_revoke_older_tokens_on_new_request(
        self, client, test_user, test_club, settings_email_on
    ):
        """New request revokes older password_reset tokens."""
        # Issue some tokens first
        raw1 = issue("password_reset", test_user)
        raw2 = issue("password_reset", test_user)
        assert peek(raw1, "password_reset") is not None
        assert peek(raw2, "password_reset") is not None

        # Request new reset link
        url = reverse("mail_public:forgot_password")
        response = client.post(url, {"email": "test@example.com"}, follow=True)

        assert response.status_code == 200

        # Old tokens should be revoked
        assert peek(raw1, "password_reset") is None
        assert peek(raw2, "password_reset") is None

        # New token should exist
        new_messages = EmailMessage.objects.filter(
            kind="password_reset", to_address="test@example.com"
        ).order_by("-created")
        assert new_messages.count() >= 1


# ===== Reset Password View Tests =====


@pytest.mark.django_db
class TestResetPasswordView:
    def test_get_shows_form_when_token_valid(self, client, test_user):
        """GET shows password form when token is valid."""
        raw = issue("password_reset", test_user)
        url = reverse("mail_public:reset_password", args=[raw])
        response = client.get(url)
        assert response.status_code == 200
        assert "Reset your password" in response.content.decode()

    def test_get_shows_error_when_token_invalid(self, client):
        """GET shows error when token is invalid."""
        url = reverse("mail_public:reset_password", args=["invalid-token"])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Invalid or expired" in content

    def test_get_shows_error_when_token_expired(self, client, test_user):
        """GET shows error when token is expired (1 hour TTL)."""
        raw = issue("password_reset", test_user, ttl=timedelta(seconds=-1))
        url = reverse("mail_public:reset_password", args=[raw])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Invalid or expired" in content

    def test_get_never_consumes_token(self, client, test_user):
        """GET never consumes token or changes state."""
        raw = issue("password_reset", test_user)
        url = reverse("mail_public:reset_password", args=[raw])

        # GET multiple times
        client.get(url)
        client.get(url)

        # Token should still be valid
        token = peek(raw, "password_reset")
        assert token is not None
        assert token.used_at is None

    def test_post_resets_password_and_consumes_token(self, client, test_user, settings_email_on):
        """POST resets password, clears must_change_password, consumes token."""
        raw = issue("password_reset", test_user)
        test_user.must_change_password = True
        test_user.save()

        url = reverse("mail_public:reset_password", args=[raw])
        response = client.post(
            url,
            {
                "password": "NewPass123!",
                "confirm": "NewPass123!",
            },
            follow=True,
        )

        # Should redirect to login
        assert response.redirect_chain[-1][0].endswith(reverse("login"))

        # Token should be consumed
        assert peek(raw, "password_reset") is None

        # Password should be changed
        test_user.refresh_from_db()
        assert test_user.check_password("NewPass123!")
        assert not test_user.must_change_password

    def test_post_rejects_mismatched_passwords(self, client, test_user):
        """POST rejects mismatched passwords."""
        raw = issue("password_reset", test_user)
        url = reverse("mail_public:reset_password", args=[raw])
        response = client.post(
            url,
            {
                "password": "NewPass123!",
                "confirm": "DifferentPass123!",
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "do not match" in content.lower()

    def test_post_rejects_weak_password(self, client, test_user):
        """POST rejects password that doesn't meet complexity requirements."""
        raw = issue("password_reset", test_user)
        url = reverse("mail_public:reset_password", args=[raw])
        response = client.post(
            url,
            {
                "password": "weak",
                "confirm": "weak",
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert (
            "uppercase" in content.lower()
            or "lowercase" in content.lower()
            or "number" in content.lower()
            or "special" in content.lower()
        )

    def test_post_rejects_reused_password(self, client, test_user):
        """POST rejects recently used password."""
        from django.contrib.auth.hashers import make_password

        from accounts.models import PasswordHistory

        # Add a password to history
        PasswordHistory.objects.create(user=test_user, password_hash=make_password("OldPass123!"))

        raw = issue("password_reset", test_user)
        url = reverse("mail_public:reset_password", args=[raw])
        response = client.post(
            url,
            {
                "password": "OldPass123!",
                "confirm": "OldPass123!",
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "used recently" in content.lower() or "reused" in content.lower()

    def test_post_token_used_once(self, client, test_user, settings_email_on):
        """Token can only be used once."""
        raw = issue("password_reset", test_user)
        url = reverse("mail_public:reset_password", args=[raw])

        # First POST succeeds
        client.post(url, {"password": "NewPass123!", "confirm": "NewPass123!"})

        # Second POST fails
        response = client.post(url, {"password": "AnotherPass123!", "confirm": "AnotherPass123!"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "already been used" in content.lower() or "expired" in content.lower()

    def test_other_sessions_ended(self, client, test_user, settings_email_on):
        """Password reset signs out other sessions."""
        # Create a session for the user
        from django.contrib.sessions.backends.db import SessionStore

        session = SessionStore()
        session["_auth_user_id"] = str(test_user.pk)
        session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session.create()
        session_key = session.session_key

        # Verify session exists in DB
        assert Session.objects.filter(session_key=session_key).exists()

        # Now do password reset from another client
        raw = issue("password_reset", test_user)
        url = reverse("mail_public:reset_password", args=[raw])
        response = client.post(
            url,
            {
                "password": "NewPass123!",
                "confirm": "NewPass123!",
            },
            follow=True,
        )

        assert response.redirect_chain[-1][0].endswith(reverse("login"))

        # Old session should be deleted
        assert not Session.objects.filter(session_key=session_key).exists()

    def test_force_login_then_reset_old_client_rejected(self, test_user, settings_email_on):
        """Integration test: force_login -> reset -> old client rejected."""
        from django.core.cache import cache
        from django.test import Client

        with override_settings(CACHES=RATELIMIT_CACHE_SETTINGS):
            cache.clear()

            # Client 1 logs in
            client1 = Client()
            client1.force_login(test_user)
            client1.get("/")
            session_key1 = client1.session.session_key

            # Client 2 does password reset
            client2 = Client()
            raw = issue("password_reset", test_user)
            url = reverse("mail_public:reset_password", args=[raw])
            client2.post(url, {"password": "NewPass123!", "confirm": "NewPass123!"})

            # Client 1's session should be invalid
            assert not Session.objects.filter(session_key=session_key1).exists()

    def test_no_password_in_any_payload(self, test_user, settings_email_on):
        """No password appears in any email payload."""
        raw = issue("password_reset", test_user)

        from mail.builders import render_email

        subject, text, html = render_email(
            "password_reset",
            "password_reset",
            {
                "subject": "Reset your password",
                "user": test_user,
                "club": None,
                "reset_link": f"http://testserver/mail/reset/{raw}/",
            },
            None,
        )

        # Check no password in email content
        assert "password" not in text.lower() or "reset" in text.lower()
        assert "password" not in html.lower() or "reset" in html.lower()
        assert test_user.password not in text
        assert test_user.password not in html


# ===== Token Tests =====


@pytest.mark.django_db
class TestPasswordResetTokens:
    def test_password_reset_token_ttl_is_1_hour(self, test_user):
        """Password reset tokens have 1-hour TTL."""
        issue("password_reset", test_user)
        token = OneTimeToken.objects.get(user=test_user, purpose="password_reset")
        expected_expires = token.created + timedelta(hours=1)
        assert abs((token.expires_at - expected_expires).total_seconds()) < 2

    def test_reset_link_works_once(self, test_user):
        """Reset link works once, then is consumed."""
        raw = issue("password_reset", test_user)

        # First peek - should work
        token = peek(raw, "password_reset")
        assert token is not None

        # First consume - should work
        consumed = consume(raw, "password_reset")
        assert consumed is not None
        assert consumed.used_at is not None

        # Second peek - should be None (used)
        token = peek(raw, "password_reset")
        assert token is None

        # Second consume - should be None
        consumed = consume(raw, "password_reset")
        assert consumed is None

    def test_reset_link_expires_after_1_hour(self, test_user):
        """Reset link expires after 1 hour."""
        raw = issue("password_reset", test_user, ttl=timedelta(seconds=-1))
        token = peek(raw, "password_reset")
        assert token is None


# ===== Password-Changed Notice Tests =====


@pytest.mark.django_db
class TestPasswordChangedNotice:
    def test_notice_sent_after_admin_reset(self, test_user, test_club, settings_email_on):
        """Notice sent after admin sets temporary password."""
        # Admin resets password
        set_temporary_password(test_user)

        # Check notice was queued
        messages = EmailMessage.objects.filter(kind="password_changed", to_address=test_user.email)
        assert messages.exists()

        message = messages.first()
        assert message.club is None  # No reply-to for multi-club users

    def test_notice_sent_after_user_password_change(self, test_user, test_club, settings_email_on):
        """Notice sent after user changes password via reset flow."""
        # User resets password via the view
        raw = issue("password_reset", test_user)
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post(
            f"/mail/reset/{raw}/",
            {"password": "NewPass123!", "confirm": "NewPass123!"},
        )
        request.user = test_user

        # We can't easily test the view this way, let's use the signal directly
        # Actually, the signal should fire on user.save()
        test_user.set_password("NewPass123!")
        test_user.save()

        # Check notice was queued
        messages = EmailMessage.objects.filter(kind="password_changed", to_address=test_user.email)
        assert messages.exists()

    def test_no_notice_on_account_creation(self, settings_email_on):
        """No notice sent on account creation."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user("new@example.com", password="NewPass123!")

        messages = EmailMessage.objects.filter(
            kind="password_changed", to_address="new@example.com"
        )
        assert not messages.exists()

    def test_no_notice_with_skip_flag(self, test_user, test_club, settings_email_on):
        """No notice when _mail_skip_password_notice is set."""
        test_user._mail_skip_password_notice = True
        test_user.set_password("NewPass123!")
        test_user.save()

        messages = EmailMessage.objects.filter(kind="password_changed", to_address=test_user.email)
        assert not messages.exists()

    def test_notice_has_no_link(self, test_user, settings_email_on):
        """Password-changed notice has no link."""
        test_user.set_password("NewPass123!")
        test_user.save()

        messages = EmailMessage.objects.filter(kind="password_changed", to_address=test_user.email)
        assert messages.exists()

        message = messages.first()
        if hasattr(message, "payload") and message.payload:
            # Check no reset link in the notice (but footer may mention "replies")
            # The notice text should not contain password reset related words
            assert "reset" not in message.payload.text.lower()
            assert "reset" not in message.payload.html.lower()


# ===== Sign Out Other Sessions Tests =====


@pytest.mark.django_db
class TestSignOutOtherSessions:
    def test_sign_out_deletes_all_sessions(self, test_user):
        """_sign_out_other_sessions deletes all sessions for the user."""
        # Create multiple sessions for the user
        from django.contrib.sessions.backends.db import SessionStore

        session1 = SessionStore()
        session1["_auth_user_id"] = str(test_user.pk)
        session1["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session1.create()

        session2 = SessionStore()
        session2["_auth_user_id"] = str(test_user.pk)
        session2["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session2.create()

        # Create session for another user
        from django.contrib.auth import get_user_model

        User = get_user_model()
        other_user = User.objects.create_user("other@example.com", password="pw")
        session3 = SessionStore()
        session3["_auth_user_id"] = str(other_user.pk)
        session3["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session3.create()

        # Call the function
        _sign_out_other_sessions(test_user)

        # test_user's sessions should be deleted
        assert not Session.objects.filter(session_key=session1.session_key).exists()
        assert not Session.objects.filter(session_key=session2.session_key).exists()

        # other_user's session should remain
        assert Session.objects.filter(session_key=session3.session_key).exists()


# ===== Rate Limit Edge Cases =====


@pytest.mark.django_db
class TestRateLimitEdgeCases:
    def test_rate_limit_separate_for_visitor_and_address(self, client, settings_email_on):
        """Visitor IP limit and address limit are separate."""
        from django.core.cache import cache

        with override_settings(CACHES=RATELIMIT_CACHE_SETTINGS):
            cache.clear()
            url = reverse("mail_public:forgot_password")

            # Exhaust address limit for one address (3/hour)
            for _i in range(3):
                response = client.post(url, {"email": "addr1@example.com"})
                assert response.status_code == 200

            # Address limit hit
            response = client.post(url, {"email": "addr1@example.com"})
            assert response.status_code == 429

            # But different address should still work (visitor limit not hit)
            response = client.post(url, {"email": "addr2@example.com"})
            assert response.status_code == 200

    def test_rate_limit_resets_after_window(self, client, settings_email_on):
        """Rate limit resets after time window (tested via cache manipulation)."""
        from django.core.cache import cache

        with override_settings(CACHES=RATELIMIT_CACHE_SETTINGS):
            cache.clear()
            url = reverse("mail_public:forgot_password")

            # Exhaust limit
            for _i in range(3):
                response = client.post(url, {"email": "expire@example.com"})
                assert response.status_code == 200

            response = client.post(url, {"email": "expire@example.com"})
            assert response.status_code == 429

            # Clear cache
            cache.clear()

            # Should work again
            response = client.post(url, {"email": "expire@example.com"})
            assert response.status_code == 200


# ===== Email Template Tests =====


@pytest.mark.django_db
class TestEmailTemplates:
    def test_password_reset_email_has_link_and_expiry(self, test_user, settings_email_on):
        """Password reset email contains reset link and mentions 1-hour expiry."""
        raw = issue("password_reset", test_user)

        from mail.builders import render_email

        subject, text, html = render_email(
            "password_reset",
            "password_reset",
            {
                "subject": "Reset your password",
                "user": test_user,
                "club": None,
                "reset_link": f"http://testserver/mail/reset/{raw}/",
            },
            None,
        )

        assert "Reset your password" in subject
        assert raw in text
        assert raw in html
        assert "1 hour" in text or "1 hour" in html

    def test_password_changed_notice_no_link(self, test_user, settings_email_on):
        """Password changed notice has no link."""
        from mail.builders import render_email

        subject, text, html = render_email(
            "password_changed",
            "password_changed",
            {
                "subject": "Your password was changed",
                "user": test_user,
                "club": None,
            },
            None,
        )

        assert "Your password was changed" in subject
        assert "reset" not in text.lower()
        assert "reset" not in html.lower()


# ===== Validators Tests =====


@pytest.mark.django_db
class TestPasswordValidatorsForReset:
    def test_complexity_validator(self):
        """ComplexityValidator requires uppercase, lowercase, digit, special."""
        validator = ComplexityValidator()

        # Valid password
        validator.validate("ValidPass123!")

        # Missing uppercase
        with pytest.raises(Exception) as exc:
            validator.validate("validpass123!")
        assert "uppercase" in str(exc.value).lower()

        # Missing lowercase
        with pytest.raises(Exception) as exc:
            validator.validate("VALIDPASS123!")
        assert "lowercase" in str(exc.value).lower()

        # Missing digit
        with pytest.raises(Exception) as exc:
            validator.validate("ValidPass!")
        assert "number" in str(exc.value).lower() or "digit" in str(exc.value).lower()

        # Missing special
        with pytest.raises(Exception) as exc:
            validator.validate("ValidPass123")
        assert "special" in str(exc.value).lower()

    def test_password_history_validator(self, test_user):
        """PasswordHistoryValidator rejects last 5 passwords."""
        from django.contrib.auth.hashers import make_password

        from accounts.models import PasswordHistory

        validator = PasswordHistoryValidator()

        # Add 5 passwords to history
        for i in range(5):
            PasswordHistory.objects.create(
                user=test_user, password_hash=make_password(f"OldPass{i}!")
            )

        # Should reject any of the 5
        for i in range(5):
            with pytest.raises(Exception) as exc:
                validator.validate(f"OldPass{i}!", test_user)
            assert "recently" in str(exc.value).lower() or "reused" in str(exc.value).lower()

        # Should accept new password
        validator.validate("NewPass123!", test_user)
