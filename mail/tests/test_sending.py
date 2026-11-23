"""Tests for the email sending logic."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from django.utils import timezone

from mail.models import EmailMessage, EmailPayload
from mail.sending import (
    BACKOFF_MINUTES,
    MAX_ATTEMPTS,
    delete_expired_payloads,
    schedule_send,
    send_due_messages,
    send_message,
)


@pytest.mark.django_db
class TestSendMessage:
    def test_send_message_success(self, club, settings):
        """Successful send marks message SENT, stores provider_id, deletes payload."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "from@test.com"

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )
        payload = EmailPayload.objects.create(
            message=message,
            text="Hello",
            html="<p>Hello</p>",
            reply_to="reply@test.com",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "msg_abc123"}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            send_message(message)

        message.refresh_from_db()
        assert message.status == EmailMessage.Status.SENT
        assert message.provider_id == "msg_abc123"
        assert message.sent_at is not None
        assert message.last_error == ""
        assert message.next_attempt_at is None
        # Payload should be deleted
        assert not EmailPayload.objects.filter(pk=payload.pk).exists()

    def test_send_message_failure_first_attempt(self, club, settings):
        """Failed send on first attempt records error, increments attempts, schedules retry."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "from@test.com"

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )
        EmailPayload.objects.create(
            message=message,
            text="Hello",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad request"
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "400 Bad Request", request=MagicMock(), response=mock_response
            )

            send_message(message)

        message.refresh_from_db()
        assert message.status == EmailMessage.Status.QUEUED
        assert message.attempts == 1
        assert message.last_error.startswith("http_400:")
        assert message.next_attempt_at is not None
        # Payload should still exist for retry
        assert EmailPayload.objects.filter(message=message).exists()

    def test_send_message_three_attempts_then_failed(self, club, settings):
        """After 3 failed attempts, message is marked FAILED with plain last_error."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "from@test.com"

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
            attempts=2,  # Already had 2 attempts
        )
        EmailPayload.objects.create(
            message=message,
            text="Hello",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "500 Internal Server Error", request=MagicMock(), response=mock_response
            )

            send_message(message)  # 3rd attempt

        message.refresh_from_db()
        assert message.status == EmailMessage.Status.FAILED
        assert message.attempts == 3
        assert message.last_error.startswith("http_500:")
        assert message.next_attempt_at is None
        # Payload should be deleted after final failure
        assert not EmailPayload.objects.filter(message=message).exists()

    def test_send_message_no_key_fails(self, club, settings):
        """No API key marks message failed with no_key error."""
        settings.RESEND_API_KEY = ""

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )
        EmailPayload.objects.create(
            message=message,
            text="Hello",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        send_message(message)

        message.refresh_from_db()
        assert message.status == EmailMessage.Status.FAILED
        assert message.last_error == "no_key: RESEND_API_KEY not configured"

    def test_send_message_network_error(self, club, settings):
        """Network error is recorded with 'network:' prefix."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "from@test.com"

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )
        EmailPayload.objects.create(
            message=message,
            text="Hello",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")

            send_message(message)

        message.refresh_from_db()
        assert message.last_error.startswith("network:")

    def test_send_message_max_200_chars_error(self, club, settings):
        """Error message is truncated to 200 characters."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "from@test.com"

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )
        EmailPayload.objects.create(
            message=message,
            text="Hello",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        long_error = "x" * 300
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = long_error
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "400 Bad Request", request=MagicMock(), response=mock_response
            )

            send_message(message)

        message.refresh_from_db()
        assert len(message.last_error) <= 200

    def test_send_message_already_sent_returns_early(self, club, settings):
        """Message already SENT returns early without sending again."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "from@test.com"

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.SENT,
            provider_id="already_sent",
        )
        EmailPayload.objects.create(
            message=message,
            text="Hello",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with patch("httpx.Client") as mock_client_class:
            send_message(message)
            mock_client_class.assert_not_called()

    def test_send_message_missing_payload(self, club, settings):
        """Missing payload marks message failed."""
        settings.RESEND_API_KEY = "test_key"

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )
        # No payload created

        send_message(message)

        message.refresh_from_db()
        assert message.status == EmailMessage.Status.FAILED
        assert message.last_error == "no_payload: Email payload not found"


@pytest.mark.django_db
class TestSendDueMessages:
    def test_send_due_messages_queued_and_sending(self, club, settings):
        """send_due_messages picks up QUEUED and SENDING with next_attempt_at <= now."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "from@test.com"

        now = timezone.now()

        # Queued message due now
        msg1 = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to1@test.com",
            subject="Test 1",
            status=EmailMessage.Status.QUEUED,
            next_attempt_at=now,
        )
        EmailPayload.objects.create(message=msg1, text="Hello", expires_at=now + timedelta(hours=1))

        # Sending message due now
        msg2 = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to2@test.com",
            subject="Test 2",
            status=EmailMessage.Status.SENDING,
            next_attempt_at=now,
        )
        EmailPayload.objects.create(message=msg2, text="Hello", expires_at=now + timedelta(hours=1))

        # Not due yet
        msg3 = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to3@test.com",
            subject="Test 3",
            status=EmailMessage.Status.QUEUED,
            next_attempt_at=now + timedelta(hours=1),
        )
        EmailPayload.objects.create(message=msg3, text="Hello", expires_at=now + timedelta(hours=1))

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "msg_123"}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            sent, failed = send_due_messages()

        assert sent == 2
        assert failed == 0
        msg1.refresh_from_db()
        msg2.refresh_from_db()
        msg3.refresh_from_db()
        assert msg1.status == EmailMessage.Status.SENT
        assert msg2.status == EmailMessage.Status.SENT
        assert msg3.status == EmailMessage.Status.QUEUED  # Not sent yet


@pytest.mark.django_db
class TestDeleteExpiredPayloads:
    def test_delete_expired_payloads_for_non_sent_messages(self, club, settings):
        """Expired payloads for non-SENT messages are deleted."""
        settings.RESEND_API_KEY = "test_key"
        now = timezone.now()

        # Queued message with expired payload
        msg1 = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to1@test.com",
            subject="Test 1",
            status=EmailMessage.Status.QUEUED,
        )
        payload1 = EmailPayload.objects.create(
            message=msg1, text="Hello", expires_at=now - timedelta(hours=1)
        )

        # Failed message with expired payload
        msg2 = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to2@test.com",
            subject="Test 2",
            status=EmailMessage.Status.FAILED,
        )
        payload2 = EmailPayload.objects.create(
            message=msg2, text="Hello", expires_at=now - timedelta(hours=1)
        )

        # Sent message with expired payload (should NOT be deleted)
        msg3 = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to3@test.com",
            subject="Test 3",
            status=EmailMessage.Status.SENT,
        )
        payload3 = EmailPayload.objects.create(
            message=msg3, text="Hello", expires_at=now - timedelta(hours=1)
        )

        # Not expired payload
        msg4 = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to4@test.com",
            subject="Test 4",
            status=EmailMessage.Status.QUEUED,
        )
        payload4 = EmailPayload.objects.create(
            message=msg4, text="Hello", expires_at=now + timedelta(hours=1)
        )

        deleted = delete_expired_payloads()

        assert deleted == 2
        assert not EmailPayload.objects.filter(pk=payload1.pk).exists()
        assert not EmailPayload.objects.filter(pk=payload2.pk).exists()
        assert EmailPayload.objects.filter(pk=payload3.pk).exists()
        assert EmailPayload.objects.filter(pk=payload4.pk).exists()

    def test_payload_deleted_after_24_hours(self, club, settings):
        """Payload is deleted after 24 hours (expires_at < now)."""
        settings.RESEND_API_KEY = "test_key"
        now = timezone.now()

        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )
        payload = EmailPayload.objects.create(
            message=message,
            text="Hello",
            expires_at=now - timedelta(hours=25),  # Expired 25 hours ago
        )

        deleted = delete_expired_payloads()

        assert deleted == 1
        assert not EmailPayload.objects.filter(pk=payload.pk).exists()


@pytest.mark.django_db
class TestBackoffSchedule:
    def test_backoff_times(self):
        """Backoff schedule is 1, 5, 30 minutes."""
        assert BACKOFF_MINUTES == [1, 5, 30]

    def test_max_attempts_is_three(self):
        """MAX_ATTEMPTS is 3."""
        assert MAX_ATTEMPTS == 3


@pytest.mark.django_db
class TestScheduleSend:
    @patch("mail.sending.transaction.on_commit")
    def test_schedule_send_uses_on_commit(self, mock_on_commit, club):
        """schedule_send uses transaction.on_commit."""
        message = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
        )

        schedule_send(message)

        mock_on_commit.assert_called_once()
