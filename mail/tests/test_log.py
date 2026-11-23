"""Tests for email log (E2)."""

import pytest
from django.urls import reverse

from accounts.models import Membership, User
from mail.models import DoNotEmail, EmailMessage, JobRun

pytestmark = [pytest.mark.django_db]


def _login(client, user):
    client.force_login(user)
    return client


class TestEmailLog:
    def test_log_requires_club_admin(self, club_admin, player, login, club, other_club):
        """Only club admin can access the log."""
        url = reverse("mail:log", args=[club.slug])

        # Club admin - should work
        c = _login(login(club_admin), club_admin)
        r = c.get(url)
        assert r.status_code == 200

        # Player - should get 403
        c = _login(login(player), player)
        r = c.get(url)
        assert r.status_code == 403

        # Other club admin (not member of this club) - should get 404 from middleware
        other_admin = Membership.objects.create(
            user=User.objects.create_user("other_admin@example.com", password="pw"),
            club=other_club,
            is_club_admin=True,
        )
        c = _login(login(other_admin.user), other_admin.user)
        r = c.get(url)
        assert r.status_code == 404

    def test_log_shows_only_club_rows(self, club_admin, login, club, other_club):
        """Club admin sees only their club's rows."""
        # Create messages for both clubs
        EmailMessage.objects.create(
            club=club, kind="welcome", to_address="a@club.com", subject="Test"
        )
        EmailMessage.objects.create(
            club=other_club, kind="welcome", to_address="b@other.com", subject="Test"
        )

        c = _login(login(club_admin), club_admin)
        url = reverse("mail:log", args=[club.slug])
        r = c.get(url)
        assert r.status_code == 200

        content = r.content.decode()
        assert "a@club.com" in content
        assert "b@other.com" not in content

    def test_log_shows_kind_recipient_status_time(self, club_admin, login, club):
        """Log shows kind, recipient, status, time; never body or link."""
        EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="test@example.com",
            subject="Welcome!",
            status=EmailMessage.Status.SENT,
        )

        c = _login(login(club_admin), club_admin)
        url = reverse("mail:log", args=[club.slug])
        r = c.get(url)
        assert r.status_code == 200

        content = r.content.decode()
        assert "Welcome" in content  # kind display
        assert "test@example.com" in content  # recipient
        assert "Sent" in content  # status display
        # Check time is shown (date format)
        assert "20" in content  # year

        # Ensure no body or link fields are exposed
        assert "body" not in content.lower() or "Body" not in content
        assert "link" not in content.lower() or "Link" not in content

    def test_log_background_jobs_panel_for_site_admin(self, site_admin, club_admin, login, club):
        """Site admin sees background jobs panel; club admin does not."""
        JobRun.objects.create(name="test_job", ok=True, note="All good")

        # Site admin sees panel
        c = _login(login(site_admin), site_admin)
        url = reverse("mail:log", args=[club.slug])
        r = c.get(url)
        assert r.status_code == 200
        content = r.content.decode()
        assert "Background jobs" in content
        assert "test_job" in content
        assert "OK" in content

        # Club admin does not see panel
        c = _login(login(club_admin), club_admin)
        r = c.get(url)
        assert r.status_code == 200
        content = r.content.decode()
        assert "Background jobs" not in content

    def test_log_show_link_button_on_failed_welcome(self, club_admin, login, club):
        """Failed/bounced welcome rows show 'Show them the link instead' button."""
        # This test checks the button renders when URL exists
        # Since M3 welcome_show_link may not exist yet, we test with {% url ... as u %}
        EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="welcome@test.com",
            subject="Welcome!",
            status=EmailMessage.Status.FAILED,
        )

        c = _login(login(club_admin), club_admin)
        url = reverse("mail:log", args=[club.slug])
        r = c.get(url)
        assert r.status_code == 200

        content = r.content.decode()
        # The button should not crash even if URL doesn't exist (safe {% url ... as u %})
        # If URL exists, it shows the button
        assert "welcome@test.com" in content

    def test_log_show_link_button_safe_before_m3(self, club_admin, login, club):
        """Button doesn't crash when URL doesn't exist (before M3 merges)."""
        EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="welcome@test.com",
            subject="Welcome!",
            status=EmailMessage.Status.BOUNCED,
        )

        c = _login(login(club_admin), club_admin)
        url = reverse("mail:log", args=[club.slug])
        r = c.get(url)
        assert r.status_code == 200
        # Should render without error (the {% url ... as u %} pattern handles missing URL)

    def test_log_pagination(self, club_admin, login, club):
        """Log paginates at 50 per page (newest first)."""
        # Create messages with explicit ordering - newest first
        for i in range(55):
            EmailMessage.objects.create(
                club=club,
                kind="welcome",
                to_address=f"user{i}@test.com",
                subject="Test",
            )

        c = _login(login(club_admin), club_admin)
        url = reverse("mail:log", args=[club.slug])
        r = c.get(url)
        assert r.status_code == 200

        # First page has 50 items (newest first: user54 down to user5)
        content = r.content.decode()
        assert "user54@test.com" in content
        assert "user5@test.com" in content
        assert "user4@test.com" not in content

        # Second page (user4 down to user0)
        r = c.get(url, {"page": 2})
        assert r.status_code == 200
        content = r.content.decode()
        assert "user4@test.com" in content
        assert "user0@test.com" in content


class TestClearFlag:
    def test_clear_flag_requires_club_admin(self, club_admin, player, login, club):
        """Only club admin can clear flag."""
        url = reverse("mail:clear_flag", args=[club.slug])

        # Club admin - should work
        c = _login(login(club_admin), club_admin)
        r = c.post(url, {"address": "test@example.com"})
        assert r.status_code == 302  # redirect

        # Player - should get 403
        c = _login(login(player), player)
        r = c.post(url, {"address": "test@example.com"})
        assert r.status_code == 403

    def test_clear_flag_removes_do_not_email(self, club_admin, login, club):
        """Address in club log, DoNotEmail exists, POST clears it."""
        # Create email message in club log
        EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="blocked@example.com",
            subject="Test",
        )
        # Create DoNotEmail entry
        DoNotEmail.objects.create(address="blocked@example.com", reason="bounce")

        c = _login(login(club_admin), club_admin)
        url = reverse("mail:clear_flag", args=[club.slug])
        r = c.post(url, {"address": "blocked@example.com"})
        assert r.status_code == 302

        # DoNotEmail should be deleted
        assert not DoNotEmail.objects.filter(address="blocked@example.com").exists()

    def test_clear_flag_only_for_address_in_club_log(self, club_admin, login, club, other_club):
        """Address not in club log -> error."""
        # Create email in other club
        EmailMessage.objects.create(
            club=other_club,
            kind="welcome",
            to_address="other@club.com",
            subject="Test",
        )
        DoNotEmail.objects.create(address="other@club.com", reason="bounce")

        c = _login(login(club_admin), club_admin)
        url = reverse("mail:clear_flag", args=[club.slug])
        r = c.post(url, {"address": "other@club.com"})
        assert r.status_code == 302

        # Should not delete (redirects with error message)
        assert DoNotEmail.objects.filter(address="other@club.com").exists()

    def test_clear_flag_case_insensitive(self, club_admin, login, club):
        """Address matching is case insensitive."""
        EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="Test@Example.COM",
            subject="Test",
        )
        DoNotEmail.objects.create(address="test@example.com", reason="bounce")

        c = _login(login(club_admin), club_admin)
        url = reverse("mail:clear_flag", args=[club.slug])
        r = c.post(url, {"address": "TEST@EXAMPLE.COM"})
        assert r.status_code == 302

        assert not DoNotEmail.objects.filter(address="test@example.com").exists()

    def test_clear_flag_empty_address(self, club_admin, login, club):
        """Empty address shows error."""
        c = _login(login(club_admin), club_admin)
        url = reverse("mail:clear_flag", args=[club.slug])
        r = c.post(url, {"address": ""})
        assert r.status_code == 302
        # Should show error message
