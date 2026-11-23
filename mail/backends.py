"""Django email backends for Resend and disabled sending."""

import logging
from typing import Any

import httpx
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage as DjangoEmailMessage

logger = logging.getLogger(__name__)


class DisabledBackend(BaseEmailBackend):
    """Email backend that does nothing and never raises.

    Used when no RESEND_API_KEY is set and DEBUG is False.
    """

    def send_messages(self, email_messages: list[DjangoEmailMessage]) -> int:
        """Pretend to send all messages successfully."""
        return len(email_messages)


class ResendBackend(BaseEmailBackend):
    """Django email backend that sends via Resend's HTTPS API."""

    def __init__(self, fail_silently: bool = False, **kwargs: Any) -> None:
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "RESEND_API_KEY", "")
        self.from_email = getattr(settings, "EMAIL_FROM", "noreply@localhost")
        self.timeout = 10.0  # seconds

    def send_messages(self, email_messages: list[DjangoEmailMessage]) -> int:
        """Send messages via Resend API.

        Returns the number of successfully sent messages.
        """
        if not self.api_key:
            logger.warning("ResendBackend: no RESEND_API_KEY configured")
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                self._send_message(message)
                sent_count += 1
            except Exception as e:
                if not self.fail_silently:
                    raise
                logger.exception("Failed to send email via Resend: %s", e)
        return sent_count

    def _send_message(self, message: DjangoEmailMessage) -> str:
        """Send a single message via Resend API.

        Returns the provider message ID.
        """
        # Use message.from_email if explicitly set, otherwise fall back to EMAIL_FROM.
        # Django defaults from_email to DEFAULT_FROM_EMAIL when None is passed,
        # so we check for that to determine if the sender explicitly set it.
        default_from = getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost")
        from_email = message.from_email
        if from_email is None or from_email == default_from:
            from_email = self.from_email

        # Build the request payload
        payload = {
            "from": from_email,
            "to": list(message.to),
            "subject": message.subject,
        }

        # Add reply-to if present
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        # Add text and HTML bodies
        if message.body:
            payload["text"] = message.body

        # Check for HTML alternative
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["html"] = content
                break

        # Send via httpx
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("id", "")
