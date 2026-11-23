"""Email sending logic for Resend backend.

This module handles the actual sending of queued emails, retry logic,
and payload cleanup.
"""

import logging
import threading
from datetime import timedelta

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import EmailMessage, EmailPayload

logger = logging.getLogger(__name__)

# Backoff schedule in minutes: 1, 5, 30
BACKOFF_MINUTES = [1, 5, 30]
MAX_ATTEMPTS = 3


def schedule_send(message: EmailMessage) -> None:
    """Schedule an email to be sent after the current transaction commits.

    Uses transaction.on_commit to ensure the message is committed,
    then spawns a short-lived background thread to send it.
    """

    def _send_in_background() -> None:
        # Small delay to let the transaction fully settle
        send_message(message)

    transaction.on_commit(lambda: threading.Thread(target=_send_in_background, daemon=True).start())


def send_message(message: EmailMessage) -> None:
    """Send a single email message via Resend API.

    Updates the message status and handles retries on failure.
    Deletes the payload after send (success or final failure).
    """
    # Refresh from DB to get latest state
    message.refresh_from_db()

    if message.status == EmailMessage.Status.SENT:
        return

    if message.status == EmailMessage.Status.FAILED:
        return

    # Mark as sending
    message.status = EmailMessage.Status.SENDING
    message.attempts += 1
    message.save(update_fields=["status", "attempts"])

    # Get the payload
    try:
        payload = message.payload
    except EmailPayload.DoesNotExist:
        message.status = EmailMessage.Status.FAILED
        message.last_error = "no_payload: Email payload not found"
        message.save(update_fields=["status", "last_error"])
        return

    # Build Resend API request
    api_key = getattr(settings, "RESEND_API_KEY", "")
    if not api_key:
        # Missing API key is a permanent failure, not retryable
        message.status = EmailMessage.Status.FAILED
        message.last_error = "no_key: RESEND_API_KEY not configured"
        message.next_attempt_at = None
        message.save(update_fields=["status", "last_error", "next_attempt_at"])
        # Delete payload after permanent failure
        try:
            message.payload.delete()
        except EmailPayload.DoesNotExist:
            pass
        return

    from_email = getattr(settings, "EMAIL_FROM", "noreply@localhost")
    to_address = message.to_address
    subject = message.subject

    request_payload = {
        "from": from_email,
        "to": [to_address],
        "subject": subject,
    }

    if payload.reply_to:
        request_payload["reply_to"] = [payload.reply_to]

    request_payload["text"] = payload.text
    if payload.html:
        request_payload["html"] = payload.html

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                "https://api.resend.com/emails",
                json=request_payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            provider_id = data.get("id", "")

        # Success!
        message.status = EmailMessage.Status.SENT
        message.provider_id = provider_id
        message.sent_at = timezone.now()
        message.last_error = ""
        message.next_attempt_at = None
        message.save(
            update_fields=[
                "status",
                "provider_id",
                "sent_at",
                "last_error",
                "next_attempt_at",
            ]
        )

        # Delete payload after successful send
        payload.delete()

    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        error_text = e.response.text[:200]
        _handle_failure(message, f"http_{error_code}: {error_text}")

    except httpx.RequestError as e:
        _handle_failure(message, f"network: {type(e).__name__}")

    except Exception as e:
        _handle_failure(message, f"error: {type(e).__name__}")


def _handle_failure(message: EmailMessage, error: str) -> None:
    """Handle a send failure: record error, schedule retry or mark failed."""
    # Truncate error to 200 chars
    if len(error) > 200:
        error = error[:200]

    message.last_error = error

    if message.attempts >= MAX_ATTEMPTS:
        # No more retries
        message.status = EmailMessage.Status.FAILED
        message.next_attempt_at = None
        message.save(update_fields=["status", "last_error", "next_attempt_at"])
        # Delete payload after final failure
        try:
            message.payload.delete()
        except EmailPayload.DoesNotExist:
            pass
    else:
        # Schedule retry
        idx = message.attempts - 1
        if idx < len(BACKOFF_MINUTES):
            backoff_minutes = BACKOFF_MINUTES[idx]
        else:
            backoff_minutes = BACKOFF_MINUTES[-1]
        message.next_attempt_at = timezone.now() + timedelta(minutes=backoff_minutes)
        message.status = EmailMessage.Status.QUEUED
        message.save(update_fields=["status", "last_error", "next_attempt_at"])
        # Keep payload for retry


def send_due_messages() -> tuple[int, int]:
    """Send all due messages.

    Returns (sent_count, failed_count).
    """
    now = timezone.now()
    due_messages = EmailMessage.objects.filter(
        status__in=[EmailMessage.Status.QUEUED, EmailMessage.Status.SENDING],
        next_attempt_at__lte=now,
    ).select_related("payload")

    sent = 0
    failed = 0

    for message in due_messages:
        send_message(message)
        message.refresh_from_db()
        if message.status == EmailMessage.Status.SENT:
            sent += 1
        elif message.status == EmailMessage.Status.FAILED:
            failed += 1

    return sent, failed


def delete_expired_payloads() -> int:
    """Delete payloads for messages that are not SENT and have expired.

    Returns the number of deleted payloads.
    """
    now = timezone.now()
    # Find payloads where message is not SENT and payload has expired
    expired_payloads = EmailPayload.objects.filter(
        expires_at__lt=now,
    ).select_related("message")

    deleted = 0
    for payload in expired_payloads:
        if payload.message.status != EmailMessage.Status.SENT:
            payload.delete()
            deleted += 1

    return deleted
