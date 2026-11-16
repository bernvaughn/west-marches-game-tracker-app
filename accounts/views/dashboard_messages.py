"""My Messages dashboard provider showing player's sent messages."""

from dataclasses import dataclass

from django.urls import reverse
from django.utils.text import Truncator

from accounts.models import Message
from accounts.scoping import club_queryset


@dataclass
class MessagesDashboardProvider:
    """Dashboard widget showing player's sent messages with status."""

    key: str = "my_messages"
    order: int = 7
    template: str = "accounts/_dashboard_my_messages.html"

    def get_context(self, request, club, character, membership):
        messages = (
            club_queryset(request, Message)
            .filter(sender=membership)
            .select_related("character")
            .order_by("-created")[:20]
        )

        message_rows = []
        for msg in messages:
            # Subject: first 50 chars of body or "Message to Admins"
            subject = Truncator(msg.body).chars(50)
            if not subject:
                subject = "Message to Admins"

            # Status badge
            status_badge_class = self._get_status_badge_class(msg.status)

            # Admin note preview (if handled/closed)
            admin_note_preview = None
            if msg.status in (Message.Status.HANDLED, Message.Status.CLOSED):
                admin_note_preview = self._get_admin_note_preview(msg)

            message_rows.append({
                "message": msg,
                "subject": subject,
                "sent_date": msg.created,
                "status": msg.status,
                "status_display": msg.get_status_display(),
                "status_badge_class": status_badge_class,
                "admin_note_preview": admin_note_preview,
                "detail_url": reverse("accounts:message_detail", args=[club.slug, msg.pk]),
            })

        return {
            "message_rows": message_rows,
        }

    def should_show(self, request, club, character, membership):
        return (
            club_queryset(request, Message)
            .filter(sender=membership)
            .exists()
        )

    def _get_status_badge_class(self, status):
        """Return Bootstrap badge class for message status."""
        if status == Message.Status.OPEN:
            return "text-bg-warning"
        elif status == Message.Status.HANDLED:
            return "text-bg-success"
        elif status == Message.Status.CLOSED:
            return "text-bg-secondary"
        return "text-bg-light"

    def _get_admin_note_preview(self, message):
        """Get a preview of admin response from the message."""
        # Check if there are granted entries (admin responses)
        if message.granted_entries.exists():
            return "Admin response: items/coins granted"
        if message.granted_visits.exists():
            return "Admin response: map visit granted"
        if message.granted_credits.exists():
            return "Admin response: map credit granted"
        if message.granted_found_marks.exists():
            return "Admin response: map discovery granted"
        return "Admin handled this message"