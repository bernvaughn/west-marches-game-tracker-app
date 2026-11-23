"""Tests for welcome email with sign-in link (E3)."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse

from accounts.forms.people import WhitelistForm
from accounts.models import Club, Membership
from accounts.passwords import ComplexityValidator, PasswordHistoryValidator
from mail.models import EmailMessage, OneTimeToken
from mail.service import email_enabled, queue_email
from mail.tokens import consume, issue, peek, revoke_older
from mail.views.welcome import welcome_set_password, welcome_show_link, welcome_resend


@pytest.fixture
def admin_user(django_user_model):
    """Create an admin user."""
    return django_user_model.objects.create_user("admin@test.com", password="pw")


@pytest.fixture
def test_user(django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user("test@example.com", password="pw")


@pytest.fixture
def test_club(db, admin_user):
    """Create a test club with admin."""
    club = Club.objects.create(name="Test Club", slug="test-club")
    Membership.objects.create(user=admin_user, club=club, is_club_admin=True)
    return club


@pytest.fixture
def test_club_with_user(db, admin_user, test_user):
    """Create a test club with both admin and regular user."""
    club = Club.objects.create(name="Test Club", slug="test-club")
    Membership.objects.create(user=admin_user, club=club, is_club_admin=True)
    Membership.objects.create(user=test_user, club=club)
    return club


@pytest.fixture
def client_with_admin(client, admin_user):
    """Client logged in as admin."""
    client.force_login(admin_user)
    return client


@pytest.fixture
def settings_email_on(settings):
    """Enable email for tests."""
    settings.MAIL_ENABLED = True
    return settings


# ===== Form Tests =====

@pytest.mark.django_db
class TestWhitelistForm:
    def test_send_welcome_link_field_exists(self):
        """Form has send_welcome_link checkbox field."""
        form = WhitelistForm()
        assert "send_welcome_link" in form.fields
        field = form.fields["send_welcome_link"]
        assert field.label == "Email them a sign-in link"
        assert "7-day sign-in link" in field.help_text
        assert field.required is False

    def test_send_welcome_link_default_when_email_on(self, settings_email_on):
        """Checkbox defaults to True when email is enabled."""
        form = WhitelistForm()
        assert form.fields["send_welcome_link"].initial is True

    def test_send_welcome_link_default_when_email_off(self, settings):
        """Checkbox defaults to False when email is disabled."""
        settings.MAIL_ENABLED = False
        form = WhitelistForm()
        assert form.fields["send_welcome_link"].initial is False


# ===== Token Tests =====

@pytest.mark.django_db
class TestWelcomeTokens:
    def test_welcome_token_ttl_is_7_days(self, test_user):
        """Welcome tokens have 7-day TTL."""
        raw = issue("welcome", test_user)
        token = OneTimeToken.objects.get(user=test_user, purpose="welcome")
        expected_expires = token.created + timedelta(days=7)
        assert abs((token.expires_at - expected_expires).total_seconds()) < 2

    def test_welcome_link_works_once(self, test_user, test_club):
        """Welcome link works once, then is consumed."""
        raw = issue("welcome", test_user, club=test_club)

        # First peek - should work
        token = peek(raw, "welcome")
        assert token is not None

        # First consume - should work
        consumed = consume(raw, "welcome")
        assert consumed is not None
        assert consumed.used_at is not None

        # Second peek - should be None (used)
        token = peek(raw, "welcome")
        assert token is None

        # Second consume - should be None
        consumed = consume(raw, "welcome")
        assert consumed is None

    def test_welcome_link_expires_after_7_days(self, test_user):
        """Welcome link expires after 7 days."""
        raw = issue("welcome", test_user, ttl=timedelta(seconds=-1))
        token = peek(raw, "welcome")
        assert token is None

    def test_resend_cancels_older_link(self, test_user, test_club):
        """Resending welcome email revokes older links."""
        raw1 = issue("welcome", test_user, club=test_club)
        raw2 = issue("welcome", test_user, club=test_club)

        # Both should be valid initially
        assert peek(raw1, "welcome") is not None
        assert peek(raw2, "welcome") is not None

        # Revoke older
        count = revoke_older("welcome", test_user, test_club)
        assert count == 2

        # Both should be revoked
        assert peek(raw1, "welcome") is None
        assert peek(raw2, "welcome") is None


# ===== Queue Email Tests =====

@pytest.mark.django_db
class TestWelcomeQueueEmail:
    def test_welcome_queued_when_email_on(self, test_club, test_user, settings_email_on):
        """Welcome email is queued when email is enabled."""
        result = queue_email(
            kind="welcome",
            to=test_user.email,
            club=test_club,
            subject="Welcome",
            text="Welcome text",
            html="<p>Welcome HTML</p>",
            user=test_user,
        )
        assert result.status == "queued"
        assert result.message is not None
        assert result.message.kind == "welcome"
        assert result.message.status == EmailMessage.Status.QUEUED

    def test_welcome_refused_for_do_not_email(self, test_club, test_user, settings_email_on):
        """Welcome email refused for do-not-email addresses."""
        from mail.suppression import suppress
        suppress(test_user.email, "manual")

        result = queue_email(
            kind="welcome",
            to=test_user.email,
            club=test_club,
            subject="Welcome",
            text="Welcome text",
            user=test_user,
        )
        assert result.status == "refused"
        assert result.message is None

    def test_welcome_refused_for_invalid_suffix(self, test_club, settings_email_on):
        """Welcome email refused for .invalid addresses."""
        result = queue_email(
            kind="welcome",
            to="test@invalid.invalid",
            club=test_club,
            subject="Welcome",
            text="Welcome text",
        )
        assert result.status == "refused"
        assert result.message is None

    def test_welcome_failed_when_email_off(self, test_club, test_user, settings):
        """Welcome email fails when email is disabled."""
        settings.MAIL_ENABLED = False
        result = queue_email(
            kind="welcome",
            to=test_user.email,
            club=test_club,
            subject="Welcome",
            text="Welcome text",
            user=test_user,
        )
        assert result.status == "failed"
        assert result.message is not None
        assert result.message.status == EmailMessage.Status.FAILED
        assert result.message.last_error == "no_key: Email is off for this site"


# ===== View Tests =====

@pytest.mark.django_db
class TestWelcomeSetPasswordView:
    def test_get_shows_form_when_token_valid(self, client, test_user, test_club):
        """GET shows password form when token is valid."""
        raw = issue("welcome", test_user, club=test_club)
        url = reverse("mail_public:welcome_set_password", args=[raw])
        response = client.get(url)
        assert response.status_code == 200
        assert "Set your password" in response.content.decode()
        assert "valid" in response.content.decode().lower() or "password" in response.content.decode().lower()

    def test_get_shows_error_when_token_invalid(self, client):
        """GET shows error when token is invalid."""
        url = reverse("mail_public:welcome_set_password", args=["invalid-token"])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Invalid or expired" in content

    def test_get_shows_error_when_token_expired(self, client, test_user):
        """GET shows error when token is expired."""
        raw = issue("welcome", test_user, ttl=timedelta(seconds=-1))
        url = reverse("mail_public:welcome_set_password", args=[raw])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Invalid or expired" in content

    def test_get_never_changes_anything(self, client, test_user, test_club):
        """GET never consumes token or changes state."""
        raw = issue("welcome", test_user, club=test_club)
        url = reverse("mail_public:welcome_set_password", args=[raw])

        # GET multiple times
        client.get(url)
        client.get(url)

        # Token should still be valid
        token = peek(raw, "welcome")
        assert token is not None
        assert token.used_at is None

    def test_post_sets_password_and_consumes_token(self, client, test_user, test_club):
        """POST sets password, clears must_change_password, consumes token."""
        raw = issue("welcome", test_user, club=test_club)
        test_user.set_password("oldpassword")
        test_user.must_change_password = True
        test_user.save()

        url = reverse("mail_public:welcome_set_password", args=[raw])
        response = client.post(url, {
            "password": "NewPass123!",
            "confirm": "NewPass123!",
        }, follow=True)

        # Should redirect to login
        assert response.redirect_chain[-1][0].endswith(reverse("account_login"))

        # Token should be consumed
        assert peek(raw, "welcome") is None

        # Password should be changed
        test_user.refresh_from_db()
        assert test_user.check_password("NewPass123!")
        assert not test_user.must_change_password

    def test_post_rejects_mismatched_passwords(self, client, test_user, test_club):
        """POST rejects mismatched passwords."""
        raw = issue("welcome", test_user, club=test_club)
        url = reverse("mail_public:welcome_set_password", args=[raw])
        response = client.post(url, {
            "password": "NewPass123!",
            "confirm": "DifferentPass123!",
        })
        assert response.status_code == 200
        content = response.content.decode()
        assert "do not match" in content.lower()

    def test_post_rejects_weak_password(self, client, test_user, test_club):
        """POST rejects password that doesn't meet complexity requirements."""
        raw = issue("welcome", test_user, club=test_club)
        url = reverse("mail_public:welcome_set_password", args=[raw])
        response = client.post(url, {
            "password": "weak",
            "confirm": "weak",
        })
        assert response.status_code == 200
        content = response.content.decode()
        assert "uppercase" in content.lower() or "lowercase" in content.lower() or "number" in content.lower() or "special" in content.lower()

    def test_post_rejects_reused_password(self, client, test_user, test_club):
        """POST rejects recently used password."""
        from accounts.models import PasswordHistory
        from django.contrib.auth.hashers import make_password

        # Add a password to history
        PasswordHistory.objects.create(user=test_user, password_hash=make_password("OldPass123!"))

        raw = issue("welcome", test_user, club=test_club)
        url = reverse("mail_public:welcome_set_password", args=[raw])
        response = client.post(url, {
            "password": "OldPass123!",
            "confirm": "OldPass123!",
        })
        assert response.status_code == 200
        content = response.content.decode()
        assert "used recently" in content.lower() or "reused" in content.lower()

    def test_post_token_used_once(self, client, test_user, test_club):
        """Token can only be used once."""
        raw = issue("welcome", test_user, club=test_club)
        url = reverse("mail_public:welcome_set_password", args=[raw])

        # First POST succeeds
        client.post(url, {"password": "NewPass123!", "confirm": "NewPass123!"})

        # Second POST fails
        response = client.post(url, {"password": "AnotherPass123!", "confirm": "AnotherPass123!"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "already been used" in content.lower() or "expired" in content.lower()

    def test_no_password_in_any_payload(self, client, test_user, test_club, settings_email_on):
        """No password appears in any email payload."""
        raw = issue("welcome", test_user, club=test_club)

        from mail.builders import render_email
        subject, text, html = render_email(
            "welcome",
            "welcome",
            {
                "subject": f"Welcome to {test_club.name}",
                "user": test_user,
                "club": test_club,
                "welcome_link": f"http://testserver/mail/welcome/{raw}/",
            },
            test_club,
        )

        # Check no password in email content
        assert "password" not in text.lower() or "set your password" in text.lower()
        assert "password" not in html.lower() or "set your password" in html.lower()
        assert test_user.password not in text
        assert test_user.password not in html


@pytest.mark.django_db
class TestWelcomeShowLinkView:
    def test_admin_can_show_fresh_link_for_failed_message(self, client_with_admin, test_club, test_user):
        """Admin can show fresh link for failed welcome message."""
        # Create a failed welcome message
        message = EmailMessage.objects.create(
            club=test_club,
            user=test_user,
            kind=EmailMessage.Kind.WELCOME,
            to_address=test_user.email,
            subject="Welcome",
            status=EmailMessage.Status.FAILED,
            last_error="no_key: Email is off for this site",
        )

        url = reverse("mail:welcome_show_link", args=[test_club.slug, message.pk])
        response = client_with_admin.post(url, follow=True)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Welcome email resent" in content or "Fresh sign-in link" in content
        assert "mail/welcome/" in content

    def test_admin_cannot_show_link_for_sent_message(self, client_with_admin, test_club, test_user):
        """Admin cannot show link for already sent message."""
        message = EmailMessage.objects.create(
            club=test_club,
            user=test_user,
            kind=EmailMessage.Kind.WELCOME,
            to_address=test_user.email,
            subject="Welcome",
            status=EmailMessage.Status.SENT,
        )

        url = reverse("mail:welcome_show_link", args=[test_club.slug, message.pk])
        response = client_with_admin.post(url, follow=True)

        # Should redirect with error
        assert response.redirect_chain[-1][0].endswith(reverse("accounts:whitelist", args=[test_club.slug]))

    def test_admin_only_for_that_club(self, client_with_admin, admin_user, test_user):
        """Admin of one club cannot show link for another club's message."""
        club1 = Club.objects.create(name="Club 1", slug="club-1")
        club2 = Club.objects.create(name="Club 2", slug="club-2")
        Membership.objects.create(user=admin_user, club=club1, is_club_admin=True)
        Membership.objects.create(user=test_user, club=club2)

        message = EmailMessage.objects.create(
            club=club2,
            user=test_user,
            kind=EmailMessage.Kind.WELCOME,
            to_address=test_user.email,
            subject="Welcome",
            status=EmailMessage.Status.FAILED,
        )

        url = reverse("mail:welcome_show_link", args=[club1.slug, message.pk])
        response = client_with_admin.post(url)
        assert response.status_code == 404

    def test_never_cached(self, client_with_admin, test_club, test_user):
        """Response is never cached."""
        message = EmailMessage.objects.create(
            club=test_club,
            user=test_user,
            kind=EmailMessage.Kind.WELCOME,
            to_address=test_user.email,
            subject="Welcome",
            status=EmailMessage.Status.FAILED,
        )

        url = reverse("mail:welcome_show_link", args=[test_club.slug, message.pk])
        response = client_with_admin.post(url)

        assert "Cache-Control" in response.headers
        assert "no-cache" in response.headers["Cache-Control"] or "no-store" in response.headers["Cache-Control"]


@pytest.mark.django_db
class TestWelcomeResendView:
    def test_admin_can_resend_welcome(self, client_with_admin, test_club, test_user, settings_email_on):
        """Admin can resend welcome email from People page."""
        # Create a membership without a welcome message (simulating existing member)
        membership = Membership.objects.get(user=test_user, club=test_club)

        url = reverse("mail:welcome_resend", args=[test_club.slug])
        response = client_with_admin.post(url, {"membership_pk": membership.pk}, follow=True)

        assert response.redirect_chain[-1][0].endswith(reverse("accounts:member_list", args=[test_club.slug]))
        # Check a welcome message was queued
        assert EmailMessage.objects.filter(
            club=test_club, user=test_user, kind=EmailMessage.Kind.WELCOME
        ).exists()

    def test_resend_revokes_older_links(self, client_with_admin, test_club, test_user, settings_email_on):
        """Resend revokes older welcome links."""
        # Issue some tokens first
        raw1 = issue("welcome", test_user, club=test_club)
        raw2 = issue("welcome", test_user, club=test_club)
        assert peek(raw1, "welcome") is not None
        assert peek(raw2, "welcome") is not None

        membership = Membership.objects.get(user=test_user, club=test_club)
        url = reverse("mail:welcome_resend", args=[test_club.slug])
        client_with_admin.post(url, {"membership_pk": membership.pk})

        # Old tokens should be revoked
        assert peek(raw1, "welcome") is None
        assert peek(raw2, "welcome") is None

        # New token should exist
        new_messages = EmailMessage.objects.filter(
            club=test_club, user=test_user, kind=EmailMessage.Kind.WELCOME
        ).order_by("-created")
        assert new_messages.count() >= 1


@pytest.mark.django_db
class TestExistingAccountAddedToClub:
    def test_existing_account_gets_added_to_club_email_no_link(self, client_with_admin, test_club, test_user, settings_email_on):
        """Existing account added to club gets 'added_to_club' email with no link."""
        # User already exists and is member of another club
        other_club = Club.objects.create(name="Other Club", slug="other-club")
        Membership.objects.create(user=test_user, club=other_club)

        # Add to test_club via whitelist
        url = reverse("accounts:whitelist", args=[test_club.slug])
        response = client_with_admin.post(url, {
            "email": test_user.email,
            "display_name": "Test User",
            "is_club_admin": False,
            "is_game_master": False,
            "character_name": "",
            "send_welcome_link": True,
        }, follow=True)

        assert response.redirect_chain[-1][0].endswith(reverse("accounts:whitelist", args=[test_club.slug]))

        # Check an "added_to_club" kind email was queued (actually uses welcome kind but different template)
        # The template used is added_to_club, which has no link
        messages_qs = EmailMessage.objects.filter(
            club=test_club, user=test_user, kind=EmailMessage.Kind.WELCOME
        )
        assert messages_qs.exists()

        # Check the payload has no welcome link
        message = messages_qs.first()
        if hasattr(message, "payload") and message.payload:
            assert "welcome" not in message.payload.text.lower() or "sign-in link" not in message.payload.text.lower()

    def test_refused_queue_shows_reason_and_temp_password(self, client_with_admin, test_club, settings):
        """When queue_email refuses, admin sees reason and temporary password."""
        settings.MAIL_ENABLED = False

        url = reverse("accounts:whitelist", args=[test_club.slug])
        response = client_with_admin.post(url, {
            "email": "newuser@example.com",
            "display_name": "New User",
            "is_club_admin": False,
            "is_game_master": False,
            "character_name": "",
            "send_welcome_link": True,
        })

        # Should show the whitelist page with temp password
        assert response.status_code == 200
        content = response.content.decode()
        assert "temporary password" in content.lower() or "temp_password" in content.lower()


# ===== Password Validator Tests =====

@pytest.mark.django_db
class TestPasswordValidators:
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
        from accounts.models import PasswordHistory
        from django.contrib.auth.hashers import make_password

        validator = PasswordHistoryValidator()

        # Add 5 passwords to history
        for i in range(5):
            PasswordHistory.objects.create(user=test_user, password_hash=make_password(f"OldPass{i}!"))

        # Should reject any of the 5
        for i in range(5):
            with pytest.raises(Exception) as exc:
                validator.validate(f"OldPass{i}!", test_user)
            assert "recently" in str(exc.value).lower() or "reused" in str(exc.value).lower()

        # Should accept new password
        validator.validate("NewPass123!", test_user)