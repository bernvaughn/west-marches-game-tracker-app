"""Tests for Resend webhook (E2)."""

import base64
import hashlib
import hmac
import time

import pytest
from django.urls import reverse

from mail.models import DoNotEmail, EmailMessage

pytestmark = [pytest.mark.django_db]


# Resend/Svix secret format: "whsec_" + base64 of the real key bytes.
SECRET = "whsec_" + base64.b64encode(b"test_secret_123").decode()


def _make_signature(secret, svix_id, svix_timestamp, body):
    """Compute a Svix signature the way Resend does: base64 HMAC keyed by the decoded secret."""
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed_payload = f"{svix_id}.{svix_timestamp}.{body}".encode()
    return base64.b64encode(hmac.new(key, signed_payload, hashlib.sha256).digest()).decode()


@pytest.fixture(autouse=True)
def _set_webhook_secret(settings):
    """Set the webhook secret for all tests."""
    settings.RESEND_WEBHOOK_SECRET = SECRET


class TestResendWebhook:
    def test_webhook_rejects_missing_secret(self, client, settings):
        """When RESEND_WEBHOOK_SECRET unset, returns 401."""
        settings.RESEND_WEBHOOK_SECRET = ""
        url = reverse("mail_public:webhook_resend")
        r = client.post(
            url,
            data='{"type": "email.delivered", "data": {"email_id": "test-123"}}',
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=str(int(time.time())),
            HTTP_SVIX_SIGNATURE="v1=invalid",
        )
        assert r.status_code == 401

    def test_webhook_rejects_missing_headers(self, client):
        """Missing svix-id/timestamp/signature -> 401."""
        url = reverse("mail_public:webhook_resend")

        # Missing svix-id
        r = client.post(
            url,
            data='{"type": "email.delivered", "data": {"email_id": "test-123"}}',
            content_type="application/json",
            HTTP_SVIX_TIMESTAMP=str(int(time.time())),
            HTTP_SVIX_SIGNATURE="v1=sig",
        )
        assert r.status_code == 401

        # Missing svix-timestamp
        r = client.post(
            url,
            data='{"type": "email.delivered", "data": {"email_id": "test-123"}}',
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_SIGNATURE="v1=sig",
        )
        assert r.status_code == 401

        # Missing svix-signature
        r = client.post(
            url,
            data='{"type": "email.delivered", "data": {"email_id": "test-123"}}',
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=str(int(time.time())),
        )
        assert r.status_code == 401

    def test_webhook_rejects_old_timestamp(self, client):
        """Timestamp >5 min old -> 401."""
        url = reverse("mail_public:webhook_resend")
        old_timestamp = str(int(time.time()) - 400)  # > 5 min
        body = '{"type": "email.delivered", "data": {"email_id": "test-123"}}'
        sig = _make_signature(SECRET, "msg_123", old_timestamp, body)

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=old_timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 401

    def test_webhook_rejects_future_timestamp(self, client):
        """Timestamp >5 min in future -> 401."""
        url = reverse("mail_public:webhook_resend")
        future_timestamp = str(int(time.time()) + 400)  # > 5 min
        body = '{"type": "email.delivered", "data": {"email_id": "test-123"}}'
        sig = _make_signature(SECRET, "msg_123", future_timestamp, body)

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=future_timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 401

    def test_webhook_rejects_bad_signature(self, client):
        """Wrong signature -> 401."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered", "data": {"email_id": "test-123"}}'
        # Wrong signature
        sig = "wrong_signature"

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 401

    def test_webhook_accepts_valid_signature(self, client):
        """Computes signature with test secret, processes event."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered", "data": {"email_id": "test-123"}}'
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        # Create a message with this provider_id
        EmailMessage.objects.create(
            provider_id="test-123",
            kind="welcome",
            to_address="test@example.com",
            subject="Test",
        )

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 200

    def test_webhook_delivered_updates_status(self, client):
        """Delivered event -> status=sent, last_error='delivered'."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered", "data": {"email_id": "prov-456"}}'
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        msg = EmailMessage.objects.create(
            provider_id="prov-456",
            kind="welcome",
            to_address="test@example.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 200

        msg.refresh_from_db()
        assert msg.status == EmailMessage.Status.SENT
        assert msg.sent_at is not None
        assert msg.last_error == "delivered"

    def test_webhook_bounced_adds_do_not_email(self, client):
        """Bounced event -> status=bounced, DoNotEmail created."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.bounced", "data": {"email_id": "prov-789"}}'
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        msg = EmailMessage.objects.create(
            provider_id="prov-789",
            kind="welcome",
            to_address="bounced@example.com",
            subject="Test",
            status=EmailMessage.Status.SENT,
        )

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 200

        msg.refresh_from_db()
        assert msg.status == EmailMessage.Status.BOUNCED

        # DoNotEmail should be created with reason=bounce
        dne = DoNotEmail.objects.get(address="bounced@example.com")
        assert dne.reason == DoNotEmail.Reason.BOUNCE

    def test_webhook_complained_adds_do_not_email(self, client):
        """Complained event -> status=complained, DoNotEmail created."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.complained", "data": {"email_id": "prov-999"}}'
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        msg = EmailMessage.objects.create(
            provider_id="prov-999",
            kind="welcome",
            to_address="complained@example.com",
            subject="Test",
            status=EmailMessage.Status.SENT,
        )

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 200

        msg.refresh_from_db()
        assert msg.status == EmailMessage.Status.COMPLAINED

        # DoNotEmail should be created with reason=complaint
        dne = DoNotEmail.objects.get(address="complained@example.com")
        assert dne.reason == DoNotEmail.Reason.COMPLAINT

    def test_webhook_unknown_provider_id_acks(self, client):
        """Unknown provider_id returns 200 (no error)."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered", "data": {"email_id": "unknown-123"}}'
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        # Should acknowledge but not error
        assert r.status_code == 200

    def test_webhook_non_post_rejected(self, client):
        """Non-POST methods return 405."""
        url = reverse("mail_public:webhook_resend")
        r = client.get(url)
        assert r.status_code == 405

    def test_webhook_invalid_json(self, client):
        """Invalid JSON returns 400."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = "not valid json"
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 400

    def test_webhook_missing_email_id(self, client):
        """Missing email_id in payload returns 400."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered"}'
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 400

    def test_webhook_accepts_any_matching_signature_in_list(self, client):
        """Svix sends space-separated signatures during key rotation; any v1 match passes."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered", "data": {"email_id": "test-123"}}'
        good = _make_signature(SECRET, "msg_123", timestamp, body)

        EmailMessage.objects.create(
            provider_id="test-123",
            kind="welcome",
            to_address="test@example.com",
            subject="Test",
        )

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= v1,{good}",
        )
        assert r.status_code == 200

    def test_webhook_rejects_signature_without_v1_prefix(self, client):
        """A bare signature with no 'v1,' version is not a Svix signature."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered", "data": {"email_id": "test-123"}}'
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=sig,
        )
        assert r.status_code == 401

    def test_webhook_rejects_old_hex_scheme(self, client, settings):
        """The signature scheme the app used before (hex HMAC of the raw secret) is rejected."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered", "data": {"email_id": "test-123"}}'
        signed = f"msg_123.{timestamp}.{body}".encode()
        old = hmac.new(SECRET.encode(), signed, hashlib.sha256).hexdigest()

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1={old}",
        )
        assert r.status_code == 401

    def test_webhook_secret_not_base64_is_rejected(self, client, settings):
        """A misconfigured secret (not whsec_ + base64) fails closed with 401."""
        settings.RESEND_WEBHOOK_SECRET = "whsec_not base64 !!"
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.delivered", "data": {"email_id": "test-123"}}'

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE="v1,AAAA",
        )
        assert r.status_code == 401

    def test_webhook_real_resend_payload_shape(self, client):
        """A full Resend-style event: email_id lives under data, with other fields beside it."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = (
            '{"type": "email.delivered", "created_at": "2026-11-24T18:31:25.720Z", '
            '"data": {"created_at": "2026-11-24T18:31:25.166Z", "email_id": "prov-real", '
            '"from": "Downtime Market <noreply@mail.downtimemarket.com>", '
            '"to": ["gm@example.com"], "subject": "Test email"}}'
        )
        sig = _make_signature(SECRET, "msg_123", timestamp, body)
        msg = EmailMessage.objects.create(
            provider_id="prov-real",
            kind="test",
            to_address="gm@example.com",
            subject="Test email",
        )

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 200
        msg.refresh_from_db()
        assert msg.status == EmailMessage.Status.SENT

    def test_webhook_bounce_updates_existing_dne(self, client):
        """Bounce updates reason if DoNotEmail already exists with different reason."""
        url = reverse("mail_public:webhook_resend")
        timestamp = str(int(time.time()))
        body = '{"type": "email.bounced", "data": {"email_id": "prov-bounce"}}'
        sig = _make_signature(SECRET, "msg_123", timestamp, body)

        EmailMessage.objects.create(
            provider_id="prov-bounce",
            kind="welcome",
            to_address="existing@example.com",
            subject="Test",
            status=EmailMessage.Status.SENT,
        )
        # Pre-existing DoNotEmail with manual reason
        DoNotEmail.objects.create(address="existing@example.com", reason="manual")

        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_123",
            HTTP_SVIX_TIMESTAMP=timestamp,
            HTTP_SVIX_SIGNATURE=f"v1,{sig}",
        )
        assert r.status_code == 200

        dne = DoNotEmail.objects.get(address="existing@example.com")
        assert dne.reason == DoNotEmail.Reason.BOUNCE
