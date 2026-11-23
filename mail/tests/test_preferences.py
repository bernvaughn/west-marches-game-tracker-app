"""Tests for email preferences and unsubscribe (E8/M9)."""

from datetime import timedelta

import pytest
from django.urls import reverse

from accounts.models import Club, Membership
from mail.models import DoNotEmail, EmailPreference, OneTimeToken
from mail.preferences import unsubscribe_extra, unsubscribe_link, wants
from mail.tokens import peek

pytestmark = [pytest.mark.django_db]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def club(db):
    return Club.objects.create(name="Test Club", slug="test-club", timezone="UTC")


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        "test@example.com", password="pass12345678", display_name="Test User"
    )


@pytest.fixture
def membership(user, club):
    return Membership.objects.create(user=user, club=club)


@pytest.fixture
def gm_user(django_user_model):
    return django_user_model.objects.create_user(
        "gm@example.com", password="pass12345678", display_name="GM User"
    )


@pytest.fixture
def gm_membership(gm_user, club):
    return Membership.objects.create(user=gm_user, club=club, is_game_master=True)


# =============================================================================
# wants() tests
# =============================================================================


class TestWants:
    def test_wants_default_reminder_on(self, membership):
        """Default for reminder is True (no row)."""
        assert wants(membership, "reminder") is True

    def test_wants_default_notice_on(self, membership):
        """Default for notice is True (no row)."""
        assert wants(membership, "notice") is True

    def test_wants_default_digest_off(self, membership):
        """Default for digest is False (opt-in)."""
        assert wants(membership, "digest") is False

    def test_wants_stored_row_enabled(self, membership):
        """Stored row with enabled=True returns True."""
        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=True)
        assert wants(membership, "reminder") is True

    def test_wants_stored_row_disabled(self, membership):
        """Stored row with enabled=False returns False."""
        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=False)
        assert wants(membership, "reminder") is False

    def test_wants_digest_enabled_for_gm(self, gm_membership):
        """GM digest can be enabled via stored row."""
        EmailPreference.objects.create(membership=gm_membership, kind="digest", enabled=True)
        assert wants(gm_membership, "digest") is True

    def test_wants_per_club_isolation(self, user):
        """Preferences are per club (per membership)."""
        club1 = Club.objects.create(name="Club 1", slug="club-1", timezone="UTC")
        club2 = Club.objects.create(name="Club 2", slug="club-2", timezone="UTC")

        m1 = Membership.objects.create(user=user, club=club1)
        m2 = Membership.objects.create(user=user, club=club2)

        EmailPreference.objects.create(membership=m1, kind="reminder", enabled=False)

        assert wants(m1, "reminder") is False
        assert wants(m2, "reminder") is True  # Different club, default on


# =============================================================================
# unsubscribe_link() tests
# =============================================================================


class TestUnsubscribeLink:
    def test_unsubscribe_link_returns_absolute_url(self, membership, settings):
        """Returns absolute URL with token."""
        settings.SITE_URL = "https://example.com"
        url = unsubscribe_link(membership.user, membership.club, "reminder")

        assert url.startswith("https://example.com/mail/unsubscribe/")
        assert len(url) > len("https://example.com/mail/unsubscribe/")

    def test_unsubscribe_link_creates_token(self, membership):
        """Creates a OneTimeToken with correct purpose and extra."""
        url = unsubscribe_link(membership.user, membership.club, "reminder")
        url.split("/mail/unsubscribe/")[1].rstrip("/")

        token = OneTimeToken.objects.get(token_hash__isnull=False, purpose="unsubscribe")
        assert token.user == membership.user
        assert token.club == membership.club
        assert token.extra == {"kind": "reminder", "membership_id": membership.id}

    def test_unsubscribe_link_token_ttl_one_year(self, membership):
        """Token TTL is 1 year (365 days)."""
        url = unsubscribe_link(membership.user, membership.club, "reminder")
        url.split("/mail/unsubscribe/")[1].rstrip("/")

        token = OneTimeToken.objects.get(purpose="unsubscribe")
        expected_expires = token.created + timedelta(days=365)
        # Allow 1 second tolerance
        assert abs((token.expires_at - expected_expires).total_seconds()) < 2

    def test_unsubscribe_link_different_kinds_different_tokens(self, membership):
        """Different kinds produce different tokens."""
        url1 = unsubscribe_link(membership.user, membership.club, "reminder")
        url2 = unsubscribe_link(membership.user, membership.club, "digest")

        assert url1 != url2
        assert OneTimeToken.objects.filter(purpose="unsubscribe").count() == 2


# =============================================================================
# unsubscribe_extra() tests
# =============================================================================


class TestUnsubscribeExtra:
    def test_extra_returns_footer_for_enabled_kind(self, membership):
        """Extra returns unsubscribe footer when kind is enabled."""
        extra_fn = unsubscribe_extra("reminder")
        context = {"membership": membership}
        text, html = extra_fn(context)

        assert "session reminders" in text
        assert "unsubscribe here" in html
        assert "/mail/unsubscribe/" in text
        assert "/mail/unsubscribe/" in html

    def test_extra_returns_empty_for_disabled_kind(self, membership):
        """Extra returns empty when kind is disabled."""
        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=False)
        extra_fn = unsubscribe_extra("reminder")
        context = {"membership": membership}
        text, html = extra_fn(context)

        assert text == ""
        assert html == ""

    def test_extra_returns_empty_for_digest_default_off(self, gm_membership):
        """Extra returns empty for digest when default off (no row)."""
        extra_fn = unsubscribe_extra("digest")
        context = {"membership": gm_membership, "game_master": gm_membership}
        text, html = extra_fn(context)

        assert text == ""
        assert html == ""

    def test_extra_returns_footer_for_digest_when_enabled(self, gm_membership):
        """Extra returns footer for digest when enabled."""
        EmailPreference.objects.create(membership=gm_membership, kind="digest", enabled=True)
        extra_fn = unsubscribe_extra("digest")
        context = {"membership": gm_membership, "game_master": gm_membership}
        text, html = extra_fn(context)

        assert "GM digests" in text
        assert "unsubscribe here" in html

    def test_extra_resolves_membership_from_user_club(self, membership):
        """Extra resolves membership from user + club in context."""
        extra_fn = unsubscribe_extra("reminder")
        context = {"user": membership.user, "club": membership.club}
        text, html = extra_fn(context)

        assert "session reminders" in text

    def test_extra_resolves_membership_from_game_master(self, gm_membership):
        """Extra resolves membership from game_master in context."""
        extra_fn = unsubscribe_extra("digest")
        EmailPreference.objects.create(membership=gm_membership, kind="digest", enabled=True)
        context = {"game_master": gm_membership}
        text, html = extra_fn(context)

        assert "GM digests" in text

    def test_extra_returns_empty_when_no_membership_found(self):
        """Extra returns empty when no membership can be resolved."""
        extra_fn = unsubscribe_extra("reminder")
        context = {}
        text, html = extra_fn(context)

        assert text == ""
        assert html == ""

    def test_extra_registered_for_canonical_kinds(self):
        """Extras are registered for reminder, cancel, change, digest."""

        # The hooks_preferences.register() should have been called during test setup
        # but we can also test the factory directly
        for kind in ("reminder", "cancel", "change", "digest"):
            extra_fn = unsubscribe_extra(kind)
            assert callable(extra_fn)


# =============================================================================
# Preferences page tests
# =============================================================================


class TestPreferencesPage:
    def test_preferences_page_lists_kinds(self, client, membership):
        """Page lists all kinds with correct labels."""
        client.force_login(membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": membership.club.slug})
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Welcome email" in content
        assert "Password reset email" in content
        assert "Session reminders" in content
        assert "Session notices" in content

    def test_welcome_and_password_always_on_no_switch(self, client, membership):
        """Welcome and password emails show as always on with no switch."""
        client.force_login(membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": membership.club.slug})
        response = client.get(url)

        content = response.content.decode()
        # Welcome and password should have "Always on" badge, no checkbox
        assert content.count("Always on") == 2
        # Should have switches only for reminder and notice (2) - digest not shown for non-GM
        assert content.count('type="checkbox"') == 2

    def test_reminder_and_notice_default_on(self, client, membership):
        """Reminder and notice default to on (checked)."""
        client.force_login(membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": membership.club.slug})
        response = client.get(url)

        content = response.content.decode()
        # Should have checked checkboxes for reminder and notice
        # Each checkbox has id="pref-reminder" and id="pref-notice" with checked attribute
        assert 'id="pref-reminder"' in content and "checked" in content
        assert 'id="pref-notice"' in content and "checked" in content

    def test_digest_default_off(self, client, gm_membership):
        """GM digest defaults to off (unchecked) for GM."""
        client.force_login(gm_membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": gm_membership.club.slug})
        response = client.get(url)

        content = response.content.decode()
        # Digest checkbox should exist and be unchecked
        assert 'id="pref-digest"' in content
        # Should not have checked attribute for digest
        # Find the digest checkbox and verify it's not checked
        import re

        digest_checkbox = re.search(r'id="pref-digest"[^>]*', content)
        assert digest_checkbox is not None
        assert "checked" not in digest_checkbox.group()

    def test_digest_shown_only_to_gm(self, client, gm_membership, membership):
        """GM digest row only shown to game masters."""
        client.force_login(gm_membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": gm_membership.club.slug})
        response = client.get(url)

        content = response.content.decode()
        assert "GM session digest" in content

        # For non-GM (same club)
        client.force_login(membership.user)
        response = client.get(url)
        content = response.content.decode()
        # Non-GM in same club should NOT see GM digest
        assert "GM session digest" not in content

    def test_post_toggles_one_kind_only(self, client, membership):
        """POST toggles exactly one kind for that membership."""
        client.force_login(membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": membership.club.slug})

        # Turn off reminders
        response = client.post(url, {"kind": "reminder", "enabled": "off"})
        assert response.status_code == 302

        membership.refresh_from_db()
        pref = EmailPreference.objects.get(membership=membership, kind="reminder")
        assert pref.enabled is False

        # Notice should still be default on (no row)
        assert wants(membership, "notice") is True

    def test_post_does_not_affect_other_kinds(self, client, membership):
        """POST for one kind doesn't affect others."""
        client.force_login(membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": membership.club.slug})

        # Create explicit prefs for both
        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=True)
        EmailPreference.objects.create(membership=membership, kind="notice", enabled=True)

        # Turn off reminders only
        client.post(url, {"kind": "reminder", "enabled": "off"})

        reminder_pref = EmailPreference.objects.get(membership=membership, kind="reminder")
        notice_pref = EmailPreference.objects.get(membership=membership, kind="notice")
        assert reminder_pref.enabled is False
        assert notice_pref.enabled is True

    def test_gm_can_toggle_digest(self, client, gm_membership):
        """GM can toggle digest preference."""
        client.force_login(gm_membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": gm_membership.club.slug})

        # Enable digest
        response = client.post(url, {"kind": "digest", "enabled": "on"})
        assert response.status_code == 302

        pref = EmailPreference.objects.get(membership=gm_membership, kind="digest")
        assert pref.enabled is True

    def test_non_gm_cannot_toggle_digest(self, client, membership):
        """Non-GM cannot toggle digest (not shown, but also blocked if forced)."""
        client.force_login(membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": membership.club.slug})

        # Try to force POST for digest
        response = client.post(url, {"kind": "digest", "enabled": "on"})
        # Should redirect but not create preference (view blocks it)
        assert response.status_code == 302
        assert not EmailPreference.objects.filter(membership=membership, kind="digest").exists()

    def test_suppressed_shows_email_off_message(self, client, membership):
        """Suppressed email shows 'email is off for you' with no switches."""
        DoNotEmail.objects.create(address=membership.user.email, reason=DoNotEmail.Reason.BOUNCE)

        client.force_login(membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": membership.club.slug})
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Email is off for you" in content
        assert "suppression list" in content
        # No switches should be present
        assert 'type="checkbox"' not in content

    def test_invalid_suffix_shows_email_off(self, client, membership):
        """.invalid email suffix shows email off message."""
        membership.user.email = "test@invalid.invalid"
        membership.user.save()

        client.force_login(membership.user)
        url = reverse("mail:preferences", kwargs={"club_slug": membership.club.slug})
        response = client.get(url)

        content = response.content.decode()
        assert "Email is off for you" in content


# =============================================================================
# Unsubscribe view tests
# =============================================================================


class TestUnsubscribeView:
    def test_get_shows_confirm_page_signed_out(self, client, membership):
        """GET shows confirm page, works signed out."""
        # Create unsubscribe token
        url = unsubscribe_link(membership.user, membership.club, "reminder")
        token = url.split("/mail/unsubscribe/")[1].rstrip("/")

        response = client.get(reverse("mail_public:unsubscribe", kwargs={"token": token}))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Unsubscribe from session reminders" in content
        assert "Yes, unsubscribe" in content
        assert "Cancel" in content

    def test_post_consumes_token_disables_preference(self, client, membership):
        """POST consumes token and disables the preference."""
        # Enable reminder first
        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=True)
        assert wants(membership, "reminder") is True

        url = unsubscribe_link(membership.user, membership.club, "reminder")
        token = url.split("/mail/unsubscribe/")[1].rstrip("/")

        response = client.post(reverse("mail_public:unsubscribe", kwargs={"token": token}))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Unsubscribed" in content
        assert "session reminders" in content

        # Preference should be disabled
        pref = EmailPreference.objects.get(membership=membership, kind="reminder")
        assert pref.enabled is False

        # Token should be consumed
        assert peek(token, "unsubscribe") is None

    def test_token_single_use(self, client, membership):
        """Token can only be used once."""
        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=True)

        url = unsubscribe_link(membership.user, membership.club, "reminder")
        token = url.split("/mail/unsubscribe/")[1].rstrip("/")

        # First POST succeeds
        client.post(reverse("mail_public:unsubscribe", kwargs={"token": token}))

        # Second POST fails
        response = client.post(reverse("mail_public:unsubscribe", kwargs={"token": token}))
        content = response.content.decode()
        assert "already been used" in content or "Invalid link" in content

    def test_invalid_token_shows_error(self, client):
        """Invalid/expired token shows error page."""
        response = client.get(reverse("mail_public:unsubscribe", kwargs={"token": "invalid-token"}))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Invalid link" in content

    def test_expired_token_shows_error(self, client, membership):
        """Expired token shows error."""
        from mail.tokens import issue

        # Issue token with negative TTL (expired)
        raw = issue("unsubscribe", membership.user, club=membership.club, ttl=timedelta(seconds=-1))
        response = client.get(reverse("mail_public:unsubscribe", kwargs={"token": raw}))
        content = response.content.decode()
        assert "expired" in content.lower() or "invalid" in content.lower()

    def test_unsubscribe_turns_off_only_that_kind(self, client, membership):
        """Unsubscribe turns off only the specific kind."""
        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=True)
        EmailPreference.objects.create(membership=membership, kind="notice", enabled=True)

        url = unsubscribe_link(membership.user, membership.club, "reminder")
        token = url.split("/mail/unsubscribe/")[1].rstrip("/")

        response = client.post(reverse("mail_public:unsubscribe", kwargs={"token": token}))
        assert response.status_code == 200

        reminder_pref = EmailPreference.objects.get(membership=membership, kind="reminder")
        notice_pref = EmailPreference.objects.get(membership=membership, kind="notice")
        assert reminder_pref.enabled is False
        assert notice_pref.enabled is True

    def test_unsubscribe_works_for_cancel_kind(self, client, membership):
        """Unsubscribe works for cancel kind (maps to notice preference)."""
        EmailPreference.objects.create(membership=membership, kind="notice", enabled=True)

        url = unsubscribe_link(membership.user, membership.club, "cancel")
        token = url.split("/mail/unsubscribe/")[1].rstrip("/")

        response = client.post(reverse("mail_public:unsubscribe", kwargs={"token": token}))
        assert response.status_code == 200

        pref = EmailPreference.objects.get(membership=membership, kind="notice")
        assert pref.enabled is False

    def test_unsubscribe_works_for_change_kind(self, client, membership):
        """Unsubscribe works for change kind (maps to notice preference)."""
        EmailPreference.objects.create(membership=membership, kind="notice", enabled=True)

        url = unsubscribe_link(membership.user, membership.club, "change")
        token = url.split("/mail/unsubscribe/")[1].rstrip("/")

        response = client.post(reverse("mail_public:unsubscribe", kwargs={"token": token}))
        assert response.status_code == 200

        pref = EmailPreference.objects.get(membership=membership, kind="notice")
        assert pref.enabled is False

    def test_unsubscribe_works_for_digest_kind(self, client, gm_membership):
        """Unsubscribe works for digest kind (GM)."""
        EmailPreference.objects.create(membership=gm_membership, kind="digest", enabled=True)

        url = unsubscribe_link(gm_membership.user, gm_membership.club, "digest")
        token = url.split("/mail/unsubscribe/")[1].rstrip("/")

        response = client.post(reverse("mail_public:unsubscribe", kwargs={"token": token}))
        assert response.status_code == 200

        pref = EmailPreference.objects.get(membership=gm_membership, kind="digest")
        assert pref.enabled is False


# =============================================================================
# Extras registry integration tests
# =============================================================================


class TestExtrasRegistry:
    def test_extra_rendered_for_reminder_kind(self, membership):
        """Extra is rendered when render_email called with 'reminder' kind."""
        from mail.builders import render_extras

        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=True)

        text, html = render_extras("reminder", {"membership": membership})
        assert "session reminders" in text
        assert "unsubscribe here" in html

    def test_extra_not_rendered_when_disabled(self, membership):
        """Unsubscribe extra not rendered when preference is disabled."""
        from mail.builders import render_extras

        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=False)

        text, html = render_extras("reminder", {"membership": membership})
        # Unsubscribe extra should not add its content (RSVP extra may still render)
        assert "session reminders" not in text
        assert "unsubscribe here" not in html

    def test_extra_rendered_for_cancel_kind(self, membership):
        """Extra is rendered for 'cancel' kind."""
        from mail.builders import render_extras

        EmailPreference.objects.create(membership=membership, kind="notice", enabled=True)

        text, html = render_extras("cancel", {"membership": membership})
        assert "session cancellation notices" in text

    def test_extra_rendered_for_change_kind(self, membership):
        """Extra is rendered for 'change' kind."""
        from mail.builders import render_extras

        EmailPreference.objects.create(membership=membership, kind="notice", enabled=True)

        text, html = render_extras("change", {"membership": membership})
        assert "session change notices" in text

    def test_extra_rendered_for_digest_kind(self, gm_membership):
        """Extra is rendered for 'digest' kind when enabled."""
        from mail.builders import render_extras

        EmailPreference.objects.create(membership=gm_membership, kind="digest", enabled=True)

        context = {"membership": gm_membership, "game_master": gm_membership}
        text, html = render_extras("digest", context)
        assert "GM digests" in text
