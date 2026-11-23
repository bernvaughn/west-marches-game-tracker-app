"""Resend webhook endpoint for email delivery events."""

import hashlib
import hmac
import json

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from mail.models import EmailMessage
from mail.suppression import suppress


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

    # Verify signature
    body = request.body
    signed_payload = f"{svix_id}.{svix_timestamp}.{body.decode()}".encode()
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    # Signature format: "v1=<hex>" or just "<hex>"
    received = svix_signature
    if received.startswith("v1="):
        received = received[3:]

    if not hmac.compare_digest(expected, received):
        return HttpResponse(status=401)

    # Parse JSON body
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event_type = payload.get("type")
    provider_id = payload.get("email_id")

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
