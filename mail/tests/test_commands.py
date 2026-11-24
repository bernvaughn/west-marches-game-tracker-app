"""Tests for mail management commands."""

from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import httpx
import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from mail.jobs import register_job
from mail.models import EmailMessage, EmailPayload, JobRun


@pytest.mark.django_db
class TestSendQueuedEmailCommand:
    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("httpx.Client")
    def test_send_queued_email_sends_due_messages(self, mock_client_class):
        """Command sends due messages and deletes expired payloads."""
        from accounts.models import Club

        Club.objects.create(name="Test", slug="test")

        now = timezone.now()

        # Due message (explicit next_attempt_at)
        msg1 = EmailMessage.objects.create(
            kind="welcome",
            to_address="to1@test.com",
            subject="Test 1",
            status=EmailMessage.Status.QUEUED,
            next_attempt_at=now,
        )
        EmailPayload.objects.create(message=msg1, text="Hello", expires_at=now + timedelta(hours=1))

        # Message with next_attempt_at=NULL (new, never attempted) - should also be sent
        msg2 = EmailMessage.objects.create(
            kind="welcome",
            to_address="to2@test.com",
            subject="Test 2",
            status=EmailMessage.Status.QUEUED,
            next_attempt_at=None,
        )
        EmailPayload.objects.create(message=msg2, text="Hello", expires_at=now + timedelta(hours=1))

        # Expired payload for non-sent message (should be deleted by cleanup, not sent)
        msg3 = EmailMessage.objects.create(
            kind="welcome",
            to_address="to3@test.com",
            subject="Test 3",
            status=EmailMessage.Status.QUEUED,
            next_attempt_at=now + timedelta(hours=1),  # Not due yet
        )
        EmailPayload.objects.create(message=msg3, text="Hello", expires_at=now - timedelta(hours=1))

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "msg_123"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        out = StringIO()
        call_command("send_queued_email", stdout=out)

        output = out.getvalue()
        # msg1 and msg2 are sent (due now and NULL next_attempt_at)
        # msg3 is not due yet, but its expired payload is deleted
        assert "Sent: 2" in output
        assert "Failed: 0" in output
        assert "Expired payloads deleted: 1" in output

        msg1.refresh_from_db()
        msg2.refresh_from_db()
        msg3.refresh_from_db()
        assert msg1.status == EmailMessage.Status.SENT
        assert msg2.status == EmailMessage.Status.SENT
        assert msg3.status == EmailMessage.Status.QUEUED  # Not sent, not due yet

    @override_settings(RESEND_API_KEY="", EMAIL_FROM="from@test.com")
    def test_send_queued_email_no_key_fails_messages(self):
        """Command fails messages when no API key."""
        from accounts.models import Club

        Club.objects.create(name="Test", slug="test")

        now = timezone.now()
        msg = EmailMessage.objects.create(
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
            next_attempt_at=now,
        )
        EmailPayload.objects.create(message=msg, text="Hello", expires_at=now + timedelta(hours=1))

        out = StringIO()
        call_command("send_queued_email", stdout=out)

        output = out.getvalue()
        assert "Sent: 0" in output
        assert "Failed: 1" in output

        msg.refresh_from_db()
        assert msg.status == EmailMessage.Status.FAILED
        assert msg.last_error == "no_key: RESEND_API_KEY not configured"


@pytest.mark.django_db
class TestRunMailJobsCommand:
    def setup_method(self):
        # Clear registered jobs before each test
        from mail import jobs

        jobs._jobs.clear()

    def teardown_method(self):
        from mail import jobs

        jobs._jobs.clear()

    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("httpx.Client")
    def test_run_mail_jobs_runs_send_queued_email(self, mock_client_class):
        """run_mail_jobs calls send_queued_email."""
        from accounts.models import Club

        Club.objects.create(name="Test", slug="test")

        now = timezone.now()
        msg = EmailMessage.objects.create(
            kind="welcome",
            to_address="to@test.com",
            subject="Test",
            status=EmailMessage.Status.QUEUED,
            next_attempt_at=now,
        )
        EmailPayload.objects.create(message=msg, text="Hello", expires_at=now + timedelta(hours=1))

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "msg_123"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        out = StringIO()
        call_command("run_mail_jobs", stdout=out)

        output = out.getvalue()
        assert "Mail jobs completed" in output
        msg.refresh_from_db()
        assert msg.status == EmailMessage.Status.SENT

    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("httpx.Client")
    def test_run_mail_jobs_runs_registered_jobs(self, mock_client_class):
        """run_mail_jobs runs all registered jobs."""
        from accounts.models import Club

        Club.objects.create(name="Test", slug="test")

        job_results = {}

        def job1():
            job_results["job1"] = True

        def job2():
            job_results["job2"] = True

        register_job("test_job1", job1)
        register_job("test_job2", job2)

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "msg_123"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        out = StringIO()
        call_command("run_mail_jobs", stdout=out)

        assert job_results["job1"] is True
        assert job_results["job2"] is True

        # Check JobRun records
        jr1 = JobRun.objects.get(name="test_job1")
        jr2 = JobRun.objects.get(name="test_job2")
        assert jr1.ok is True
        assert jr2.ok is True

    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("httpx.Client")
    def test_run_mail_jobs_survives_failing_job(self, mock_client_class):
        """A failing job does not stop other jobs."""
        from accounts.models import Club

        Club.objects.create(name="Test", slug="test")

        job_results = {}

        def good_job():
            job_results["good"] = True

        def bad_job():
            raise ValueError("Job failed!")

        register_job("good_job", good_job)
        register_job("bad_job", bad_job)

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "msg_123"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        out = StringIO()
        err = StringIO()
        call_command("run_mail_jobs", stdout=out, stderr=err)

        assert job_results["good"] is True
        assert "bad" not in job_results

        # Check JobRun records
        good_run = JobRun.objects.get(name="good_job")
        bad_run = JobRun.objects.get(name="bad_job")
        assert good_run.ok is True
        assert bad_run.ok is False
        assert "ValueError: Job failed!" in bad_run.note

    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("httpx.Client")
    def test_run_mail_jobs_creates_job_run_records(self, mock_client_class):
        """run_mail_jobs creates/updates JobRun for each job."""
        from accounts.models import Club

        Club.objects.create(name="Test", slug="test")

        def my_job():
            pass

        register_job("my_job", my_job)

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "msg_123"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        call_command("run_mail_jobs")

        jr = JobRun.objects.get(name="my_job")
        assert jr.last_run_at is not None
        assert jr.ok is True
        assert jr.note == ""

        # Run again - should update existing record
        call_command("run_mail_jobs")
        jr.refresh_from_db()
        assert jr.ok is True


@pytest.mark.django_db
class TestSendTestEmailCommand:
    @override_settings(RESEND_API_KEY="", EMAIL_FROM="from@test.com")
    def test_send_test_email_no_key(self):
        """send_test_email prints 'bad key' when no API key."""
        out = StringIO()
        call_command("send_test_email", "test@example.com", stdout=out)

        output = out.getvalue().strip()
        assert output == "Result: bad key (no RESEND_API_KEY configured)"

    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("mail.management.commands.send_test_email.send_mail")
    def test_send_test_email_ok(self, mock_send_mail):
        """send_test_email prints 'OK' on success."""
        out = StringIO()
        call_command("send_test_email", "test@example.com", stdout=out)

        output = out.getvalue().strip()
        assert output == "Result: OK"
        mock_send_mail.assert_called_once()

    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("mail.management.commands.send_test_email.send_mail")
    def test_send_test_email_bad_key(self, mock_send_mail):
        """send_test_email prints 'bad key' on 401/unauthorized."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_send_mail.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        out = StringIO()
        call_command("send_test_email", "test@example.com", stdout=out)

        output = out.getvalue().strip()
        assert output == "Result: bad key"

    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("mail.management.commands.send_test_email.send_mail")
    def test_send_test_email_unverified_domain(self, mock_send_mail):
        """send_test_email prints 'unverified domain' on domain error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Domain not verified"
        mock_send_mail.side_effect = httpx.HTTPStatusError(
            "400 Bad Request", request=MagicMock(), response=mock_response
        )

        out = StringIO()
        call_command("send_test_email", "test@example.com", stdout=out)

        output = out.getvalue().strip()
        assert output == "Result: unverified domain"

    @override_settings(RESEND_API_KEY="test_key", EMAIL_FROM="from@test.com")
    @patch("mail.management.commands.send_test_email.send_mail")
    def test_send_test_email_other_error(self, mock_send_mail):
        """send_test_email prints generic error for other failures."""
        mock_send_mail.side_effect = ValueError("Some other error")

        out = StringIO()
        call_command("send_test_email", "test@example.com", stdout=out)

        output = out.getvalue().strip()
        assert output == "Result: error - ValueError"
