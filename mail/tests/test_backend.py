"""Tests for the Resend email backend."""

import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives

from mail.backends import DisabledBackend, ResendBackend


@pytest.mark.django_db
class TestDisabledBackend:
    def test_send_messages_returns_count(self):
        """DisabledBackend returns the count of messages without sending."""
        backend = DisabledBackend()
        messages = [
            EmailMessage("Subject 1", "Body 1", "from@test.com", ["to1@test.com"]),
            EmailMessage("Subject 2", "Body 2", "from@test.com", ["to2@test.com"]),
        ]
        count = backend.send_messages(messages)
        assert count == 2

    def test_send_messages_never_raises(self):
        """DisabledBackend never raises exceptions."""
        backend = DisabledBackend(fail_silently=False)
        messages = [EmailMessage("Subject", "Body", "from@test.com", ["to@test.com"])]
        # Should not raise
        count = backend.send_messages(messages)
        assert count == 1


@pytest.mark.django_db
class TestResendBackend:
    def test_send_messages_builds_correct_request(self, settings):
        """ResendBackend builds the right request: URL, bearer header, from."""
        settings.RESEND_API_KEY = "test_key_123"
        settings.EMAIL_FROM = "test@example.com"

        backend = ResendBackend()

        message = EmailMultiAlternatives(
            subject="Test Subject",
            body="Test body",
            from_email="sender@example.com",
            to=["recipient@example.com"],
            reply_to=["reply@example.com"],
        )
        message.attach_alternative("<p>Test HTML</p>", "text/html")

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "msg_123"}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            count = backend.send_messages([message])

            assert count == 1
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://api.resend.com/emails"
            assert call_args[1]["headers"]["Authorization"] == "Bearer test_key_123"
            assert call_args[1]["headers"]["Content-Type"] == "application/json"
            assert call_args[1]["json"]["from"] == "sender@example.com"
            assert call_args[1]["json"]["to"] == ["recipient@example.com"]
            assert call_args[1]["json"]["subject"] == "Test Subject"
            assert call_args[1]["json"]["reply_to"] == ["reply@example.com"]
            assert call_args[1]["json"]["text"] == "Test body"
            assert call_args[1]["json"]["html"] == "<p>Test HTML</p>"
            # Verify timeout was set on client
            mock_client_class.assert_called_once_with(timeout=10.0)

    def test_send_messages_uses_default_from_email(self, settings):
        """ResendBackend uses EMAIL_FROM when message has no from_email."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "default@example.com"

        backend = ResendBackend()
        message = EmailMultiAlternatives(
            subject="Test",
            body="Body",
            from_email=None,
            to=["to@test.com"],
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "msg_123"}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            backend.send_messages([message])

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["from"] == "default@example.com"

    def test_send_messages_no_key_returns_zero(self, settings, caplog):
        """ResendBackend returns 0 and logs warning when no API key."""
        settings.RESEND_API_KEY = ""
        backend = ResendBackend()
        message = EmailMessage("Test", "Body", "from@test.com", ["to@test.com"])

        with caplog.at_level(logging.WARNING):
            count = backend.send_messages([message])

        assert count == 0
        assert "no RESEND_API_KEY configured" in caplog.text

    def test_send_messages_fails_silently(self, settings):
        """ResendBackend with fail_silently=True doesn't raise on error."""
        settings.RESEND_API_KEY = "test_key"
        backend = ResendBackend(fail_silently=True)
        message = EmailMessage("Test", "Body", "from@test.com", ["to@test.com"])

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = httpx.RequestError("Network error")

            # Should not raise
            count = backend.send_messages([message])
            assert count == 0

    def test_send_messages_raises_when_not_fail_silently(self, settings):
        """ResendBackend with fail_silently=False raises on error."""
        settings.RESEND_API_KEY = "test_key"
        backend = ResendBackend(fail_silently=False)
        message = EmailMessage("Test", "Body", "from@test.com", ["to@test.com"])

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = httpx.RequestError("Network error")

            with pytest.raises(httpx.RequestError):
                backend.send_messages([message])

    def test_key_never_in_logs(self, settings, caplog):
        """API key never appears in log output."""
        settings.RESEND_API_KEY = "super_secret_key_12345"
        backend = ResendBackend()
        message = EmailMessage("Test", "Body", "from@test.com", ["to@test.com"])

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "msg_123"}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            with caplog.at_level(logging.DEBUG):
                backend.send_messages([message])

        # Key should not appear in any log message
        assert "super_secret_key_12345" not in caplog.text
        # Bearer token should not appear
        assert "Bearer super_secret_key_12345" not in caplog.text


@pytest.mark.django_db
class TestBackendSelection:
    def test_backend_classes_can_be_instantiated(self, settings):
        """ResendBackend and DisabledBackend can be instantiated."""
        settings.RESEND_API_KEY = "test_key"
        settings.EMAIL_FROM = "from@test.com"

        resend_backend = ResendBackend()
        assert resend_backend.api_key == "test_key"
        assert resend_backend.from_email == "from@test.com"

        disabled_backend = DisabledBackend()
        assert disabled_backend is not None

    def test_resend_backend_reads_api_key_from_settings(self, settings):
        """ResendBackend reads RESEND_API_KEY from settings."""
        settings.RESEND_API_KEY = "key_from_settings"
        backend = ResendBackend()
        assert backend.api_key == "key_from_settings"

    def test_disabled_backend_never_raises(self):
        """DisabledBackend never raises even with fail_silently=False."""
        backend = DisabledBackend(fail_silently=False)
        messages = [
            EmailMultiAlternatives("Subject", "Body", "from@test.com", ["to@test.com"]),
        ]
        count = backend.send_messages(messages)
        assert count == 1
