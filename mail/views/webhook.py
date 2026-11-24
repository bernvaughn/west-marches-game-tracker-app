"""Resend webhook endpoint for email delivery events."""

import base64
import binascii
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from mail.models import EmailMessage
from mail.suppression import suppress

logger = logging.getLogger(__name__)


def _signing_key(secret: str) -> bytes | None:
    """Return the Svix signing key: the base64-decoded part after ``whsec_``.

    Resend signs webhooks with Svix. The secret shown in the Resend dashboard is
    ``whsec_<base64>``, and the HMAC key is the decoded bytes, not the string.
    """
    raw = secret.removeprefix("whsec_")
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None


def _signature_matches(key: bytes, signed_payload: bytes, header: str) -> bool:
    """Check a ``svix-signature`` header: space-separated ``v1,<base64>`` entries."""
    expected = base64.b64encode(hmac.new(key, signed_payload, hashlib.sha256).digest()).decode()
    for entry in header.split():
        version, _, signature = entry.partition(",")
        if version == "v1" and hmac.compare_digest(expected, signature):
            return True
    return False


@csrf_exempt
def resend_webhook(request):
    """Handle Resend webhook events (Svix-style signatures)."""
    if request.method != "POST":
        return HttpResponse(status=405)

    # Check secret is configured
    secret = getattr(settings, "RESEND_WEBHOOK_SECRET", None)
    if not secret:
        return HttpResponse(status=401)

    # Extract Svix headers
    svix_id = request.headers.get("svix-id")
    svix_timestamp = request.headers.get("svix-timestamp")
    svix_signature = request.headers.get("svix-signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        return HttpResponse(status=401)

    # Check timestamp (reject if older than 5 minutes)
    try:
        timestamp = int(svix_timestamp)
    except ValueError:
        return HttpResponse(status=401)

    now = int(timezone.now().timestamp())
    if abs(now - timestamp) > 300:
        return HttpResponse(status=401)

    # Verify signature: HMAC-SHA256 over "<id>.<timestamp>.<body>", keyed with the
    # base64-decoded secret, compared as base64 against each "v1,<sig>" entry.
    key = _signing_key(secret)
    if key is None:
        logger.warning("RESEND_WEBHOOK_SECRET is not a valid whsec_ base64 secret")
        return HttpResponse(status=401)

    signed_payload = f"{svix_id}.{svix_timestamp}.".encode() + request.body
    if not _signature_matches(key, signed_payload, svix_signature):
        return HttpResponse(status=401)

    # Parse JSON body
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    # Resend nests the email id under "data": {"type": ..., "data": {"email_id": ...}}
    event_type = payload.get("type")
    data = payload.get("data")
    provider_id = data.get("email_id") if isinstance(data, dict) else None

    if not provider_id:
        return HttpResponse(status=400)

    # Find the email message
    message = EmailMessage.objects.filter(provider_id=provider_id).first()
    if not message:
        # Acknowledge but don't error - unknown provider_id
        return HttpResponse(status=200)

    # Update based on event type
    if event_type == "email.delivered":
        message.status = EmailMessage.Status.SENT
        message.sent_at = timezone.now()
        message.last_error = "delivered"
        message.save(update_fields=["status", "sent_at", "last_error"])

    elif event_type == "email.bounced":
        message.status = EmailMessage.Status.BOUNCED
        message.save(update_fields=["status"])
        suppress(message.to_address, "bounce")

    elif event_type == "email.complained":
        message.status = EmailMessage.Status.COMPLAINED
        message.save(update_fields=["status"])
        suppress(message.to_address, "complaint")

    return HttpResponse(status=200)
