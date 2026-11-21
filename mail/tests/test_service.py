from unittest.mock import patch

import pytest

from mail.models import ClubMailSettings, EmailMessage, EmailPayload
from mail.service import email_enabled, queue_email
from mail.suppression import suppress


@pytest.mark.django_db
class TestEmailEnabled:
    def test_email_enabled_returns_setting(self, settings):
        settings.MAIL_ENABLED = True
        assert email_enabled() is True

        settings.MAIL_ENABLED = False
        assert email_enabled() is False


@pytest.mark.django_db
class TestQueueEmail:
    def test_refused_do_not_email(self, club):
        """Queue email refuses do-not-email addresses."""
        suppress("blocked@example.com", "manual")
        result = queue_email(
            kind="welcome",
            to="blocked@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        assert result.status == "refused"
        assert result.message is None
        assert EmailMessage.objects.count() == 0

    def test_refused_invalid_suffix(self, club):
        """Queue email refuses .invalid addresses."""
        result = queue_email(
            kind="welcome",
            to="test@invalid.invalid",
            club=club,
            subject="Test",
            text="Hello",
        )
        assert result.status == "refused"
        assert result.message is None
        assert EmailMessage.objects.count() == 0

    def test_refused_case_insensitive(self, club):
        """Suppression is case insensitive."""
        suppress("BLOCKED@EXAMPLE.COM", "manual")
        result = queue_email(
            kind="welcome",
            to="blocked@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        assert result.status == "refused"

    @patch("mail.service.email_enabled", return_value=False)
    def test_failed_when_email_off(self, mock_enabled, club):
        """When email is off, stores a failed row with no payload."""
        result = queue_email(
            kind="welcome",
            to="test@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        assert result.status == "failed"
        assert result.message is not None
        msg = result.message
        assert msg.status == EmailMessage.Status.FAILED
        assert msg.last_error == "no_key: Email is off for this site"
        assert not hasattr(msg, "payload") or msg.payload is None
        # Check no payload was created
        assert EmailPayload.objects.count() == 0

    def test_queued_creates_message_and_payload(self, club, settings):
        """When email is on, creates queued message with payload."""
        settings.MAIL_ENABLED = True
        result = queue_email(
            kind="welcome",
            to="test@example.com",
            club=club,
            subject="Test Subject",
            text="Hello world",
            html="<p>Hello world</p>",
            reply_to="reply@example.com",
        )
        assert result.status == "queued"
        assert result.message is not None
        msg = result.message
        assert msg.status == EmailMessage.Status.QUEUED
        assert msg.to_address == "test@example.com"
        assert msg.subject == "Test Subject"
        assert msg.kind == "welcome"
        assert msg.club == club

        # Check payload
        payload = msg.payload
        assert payload.text == "Hello world"
        assert payload.html == "<p>Hello world</p>"
        assert payload.reply_to == "reply@example.com"
        assert payload.expires_at is not None

    def test_message_has_no_body_or_link(self, club, settings):
        """EmailMessage model has no body or link fields."""
        settings.MAIL_ENABLED = True
        queue_email(
            kind="welcome",
            to="test@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        msg = EmailMessage.objects.first()
        field_names = [f.name for f in msg._meta.get_fields()]
        assert "body" not in field_names
        assert "link" not in field_names
        assert "html" not in field_names
        assert "text" not in field_names

    @patch("mail.dispatch.after_queue")
    def test_after_queue_called_when_queued(self, mock_after_queue, club, settings):
        """after_queue is called when email is queued."""
        settings.MAIL_ENABLED = True
        queue_email(
            kind="welcome",
            to="test@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        mock_after_queue.assert_called_once()

    @patch("mail.dispatch.after_queue")
    def test_after_queue_not_called_when_failed(self, mock_after_queue, club, settings):
        """after_queue is NOT called when email is off (failed)."""
        settings.MAIL_ENABLED = False
        queue_email(
            kind="welcome",
            to="test@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        mock_after_queue.assert_not_called()

    @patch("mail.dispatch.after_queue")
    def test_after_queue_noop_when_no_sending_module(self, mock_after_queue, club, settings):
        """after_queue is a no-op when mail.sending doesn't exist (M1 state)."""
        settings.MAIL_ENABLED = True
        # In M1, mail.sending doesn't exist, so after_queue should not raise
        result = queue_email(
            kind="welcome",
            to="test@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        assert result.status == "queued"
        # after_queue was called but did nothing (import guard)
        mock_after_queue.assert_called_once()

    def test_reply_to_from_club_mail_settings(self, club, settings):
        """reply_to uses ClubMailSettings.contact_email via club_reply_to."""
        settings.MAIL_ENABLED = True
        ClubMailSettings.objects.create(club=club, contact_email="club@test.com")
        result = queue_email(
            kind="welcome",
            to="test@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        assert result.status == "queued"
        assert result.message.payload.reply_to == "club@test.com"

    def test_reply_to_none_when_no_contact_email(self, club, settings):
        """reply_to is empty when club has no contact email."""
        settings.MAIL_ENABLED = True
        ClubMailSettings.objects.create(club=club, contact_email="")
        result = queue_email(
            kind="welcome",
            to="test@example.com",
            club=club,
            subject="Test",
            text="Hello",
        )
        assert result.status == "queued"
        assert result.message.payload.reply_to == ""

    def test_reply_to_none_when_no_club(self, settings):
        """reply_to is empty when club is None."""
        settings.MAIL_ENABLED = True
        result = queue_email(
            kind="welcome",
            to="test@example.com",
            club=None,
            subject="Test",
            text="Hello",
        )
        assert result.status == "queued"
        assert result.message.payload.reply_to == ""
