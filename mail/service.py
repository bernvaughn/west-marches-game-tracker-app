"""Mail service module.

This module provides the core email queuing functionality.

The `_mail_skip_password_notice` attribute can be set on a user instance to skip
sending the password change notice email. This is used by the password reset flow
(M3) and the welcome email flow (M4) to avoid duplicate notices when the user
sets their password for the first time.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import dispatch
from .builders import club_reply_to
from .models import EmailMessage, EmailPayload, QueueResult
from .suppression import is_suppressed


def email_enabled() -> bool:
    """Check if email is enabled for this site.

    Reads MAIL_ENABLED at call time so it reflects runtime changes.
    """
    return getattr(settings, "MAIL_ENABLED", False)


def email_disabled_reason() -> str:
    """Return a user-friendly reason why email is disabled.

    Returns an empty string if email is enabled.
    """
    if email_enabled():
        return ""
    # Check the root cause: RESEND_API_KEY not configured and not in DEBUG mode
    from django.conf import settings

    resend_key = getattr(settings, "RESEND_API_KEY", None)
    debug = getattr(settings, "DEBUG", False)
    if not resend_key and not debug:
        return (
            "Email is disabled because RESEND_API_KEY is not configured. "
            "A site admin needs to set it to enable outgoing email."
        )
    return "Email is disabled for this site."


def email_can_send() -> bool:
    """True only when a real RESEND_API_KEY is configured.

    MAIL_ENABLED is also true under DEBUG, but a test email cannot actually be
    delivered without a key. Use this to decide whether the "Send test email"
    button may be enabled.
    """
    return bool(getattr(settings, "RESEND_API_KEY", ""))


def test_email_unavailable_reason() -> str:
    """User-friendly reason a test email cannot be sent right now.

    Returns an empty string when email can be sent or is fully disabled (that
    case shows the "Email is disabled" banner instead).
    """
    if email_can_send():
        return ""
    if email_enabled():
        return (
            "No RESEND_API_KEY is set. In development, emails are only logged "
            "to the server console, so a test email cannot be delivered."
        )
    return ""


def queue_email(
    kind: str,
    to: str,
    club,
    subject: str,
    text: str,
    html: str = "",
    reply_to: str | None = None,
    user=None,
    expires: timedelta | None = None,
) -> QueueResult:
    """Queue an email for delivery. Never sends directly.

    Returns a QueueResult with status:
    - "queued": email was queued for delivery
    - "refused": address is suppressed (do-not-email or .invalid)
    - "failed": email is disabled for this site

    When refused: no row is stored.
    When failed: an EmailMessage with status=failed is stored, no payload, no after_queue call.
    """
    normalized_to = to.strip().lower()

    # Check suppression
    if is_suppressed(normalized_to):
        return QueueResult(status="refused", message=None)

    # Check if email is enabled
    if not email_enabled():
        disabled_reason = email_disabled_reason()
        message = EmailMessage.objects.create(
            club=club,
            user=user,
            kind=kind,
            to_address=normalized_to,
            subject=subject,
            status=EmailMessage.Status.FAILED,
            last_error=disabled_reason or "Email is disabled for this site.",
        )
        return QueueResult(status="failed", message=message)

    # Email is enabled - queue the message
    if expires is None:
        expires = timedelta(hours=24)

    # Use club's contact email if reply_to not explicitly provided
    if reply_to is None:
        reply_to = club_reply_to(club) or ""

    with transaction.atomic():
        message = EmailMessage.objects.create(
            club=club,
            user=user,
            kind=kind,
            to_address=normalized_to,
            subject=subject,
            status=EmailMessage.Status.QUEUED,
        )
        EmailPayload.objects.create(
            message=message,
            text=text,
            html=html,
            reply_to=reply_to,
            expires_at=timezone.now() + expires,
        )

    # Notify the sending module (if it exists)
    dispatch.after_queue(message)

    return QueueResult(status="queued", message=message)
