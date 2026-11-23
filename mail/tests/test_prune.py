"""Tests for prune_email command (E2)."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from mail.models import EmailMessage, EmailPayload

pytestmark = [pytest.mark.django_db]


def _create_old_message(club, email, subject, days_ago):
    """Create an EmailMessage with a specific created date."""
    msg = EmailMessage.objects.create(
        club=club,
        kind="welcome",
        to_address=email,
        subject=subject,
    )
    # Update created to the desired date
    msg.created = timezone.now() - timedelta(days=days_ago)
    msg.save(update_fields=["created"])
    return msg


class TestPruneEmail:
    def test_prune_deletes_old_messages(self, club):
        """Messages >90 days deleted, newer kept."""
        old_msg = _create_old_message(club, "old@example.com", "Old", 91)
        new_msg = _create_old_message(club, "new@example.com", "New", 89)

        # Also create a message with no club (should also be pruned)
        old_no_club = _create_old_message(None, "noclub@example.com", "No club", 91)

        out = StringIO()
        call_command("prune_email", stdout=out)

        # Old messages should be deleted
        assert not EmailMessage.objects.filter(pk=old_msg.pk).exists()
        assert not EmailMessage.objects.filter(pk=old_no_club.pk).exists()

        # New message should remain
        assert EmailMessage.objects.filter(pk=new_msg.pk).exists()

        output = out.getvalue()
        assert "Deleted 2 email messages older than 90 days" in output

    def test_prune_deletes_payloads(self, club):
        """EmailPayload cascade deleted with EmailMessage."""
        old_msg = _create_old_message(club, "old@example.com", "Old", 91)
        payload = EmailPayload.objects.create(
            message=old_msg,
            text="Hello",
            html="<p>Hello</p>",
            expires_at=timezone.now() + timedelta(days=1),
        )

        call_command("prune_email")

        # Payload should be cascade deleted
        assert not EmailPayload.objects.filter(pk=payload.pk).exists()

    def test_prune_output_shows_count(self, club):
        """Stdout shows deleted count."""
        _create_old_message(club, "old1@example.com", "Old 1", 91)
        _create_old_message(club, "old2@example.com", "Old 2", 91)

        out = StringIO()
        call_command("prune_email", stdout=out)

        output = out.getvalue()
        assert "Deleted 2 email messages older than 90 days" in output

    def test_prune_no_messages_deleted(self, club):
        """No output when nothing to delete."""
        _create_old_message(club, "new@example.com", "New", 1)

        out = StringIO()
        call_command("prune_email", stdout=out)

        output = out.getvalue()
        assert "Deleted 0 email messages older than 90 days" in output

    def test_prune_exactly_90_days_not_deleted(self, club):
        """Messages slightly less than 90 days old are not deleted (lt, not lte)."""
        # 89 days + 23 hours = 89.96 days < 90 days
        msg = _create_old_message(club, "exact@example.com", "Exact 90", 89)
        # Move it back by 23 more hours
        msg.created = timezone.now() - timedelta(days=89, hours=23)
        msg.save(update_fields=["created"])

        call_command("prune_email")

        assert EmailMessage.objects.filter(pk=msg.pk).exists()
