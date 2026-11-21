import pytest
from django.db import IntegrityError

from accounts.models import Club, Membership, User
from mail.models import (
    ClubMailSettings,
    DoNotEmail,
    EmailMessage,
    EmailPayload,
    EmailPreference,
    JobRun,
    NoticeSent,
    OneTimeToken,
)


@pytest.mark.django_db
class TestEmailMessage:
    def test_app_label(self):
        assert EmailMessage._meta.app_label == "mail"

    def test_no_body_or_link_fields(self):
        """Ensure EmailMessage has no body or link fields."""
        field_names = [f.name for f in EmailMessage._meta.get_fields()]
        assert "body" not in field_names
        assert "link" not in field_names
        assert "html" not in field_names
        assert "text" not in field_names

    def test_club_set_null(self):
        """Club FK uses SET_NULL."""
        club = Club.objects.create(name="Test", slug="test")
        msg = EmailMessage.objects.create(
            club=club,
            kind="welcome",
            to_address="test@example.com",
            subject="Test",
        )
        club.delete()
        msg.refresh_from_db()
        assert msg.club is None

    def test_user_set_null(self):
        """User FK uses SET_NULL."""
        user = User.objects.create_user("user@example.com", password="pw")
        msg = EmailMessage.objects.create(
            user=user,
            kind="welcome",
            to_address="test@example.com",
            subject="Test",
        )
        user.delete()
        msg.refresh_from_db()
        assert msg.user is None

    def test_indexes_exist(self):
        """Check that required indexes are defined."""
        index_names = [idx.name for idx in EmailMessage._meta.indexes]
        assert "mail_msg_status_next" in index_names
        assert "mail_msg_club_created" in index_names


@pytest.mark.django_db
class TestEmailPayload:
    def test_one_to_one_with_message(self):
        msg = EmailMessage.objects.create(
            kind="welcome",
            to_address="test@example.com",
            subject="Test",
        )
        payload = EmailPayload.objects.create(
            message=msg,
            text="Hello",
            html="<p>Hello</p>",
            expires_at="2099-01-01",
        )
        assert msg.payload == payload
        assert payload.message == msg

    def test_has_reply_to_field(self):
        """EmailPayload has reply_to field (added for M2)."""
        msg = EmailMessage.objects.create(
            kind="welcome",
            to_address="test@example.com",
            subject="Test",
        )
        payload = EmailPayload.objects.create(
            message=msg,
            text="Hello",
            reply_to="reply@example.com",
            expires_at="2099-01-01",
        )
        assert payload.reply_to == "reply@example.com"


@pytest.mark.django_db
class TestDoNotEmail:
    def test_lowercase_on_save(self):
        obj = DoNotEmail.objects.create(address="TEST@EXAMPLE.COM", reason="manual")
        assert obj.address == "test@example.com"

    def test_unique_constraint(self):
        DoNotEmail.objects.create(address="test@example.com", reason="manual")
        with pytest.raises(IntegrityError):
            DoNotEmail.objects.create(address="TEST@EXAMPLE.COM", reason="bounce")


@pytest.mark.django_db
class TestOneTimeToken:
    def test_token_hash_unique(self):
        user = User.objects.create_user("user@example.com", password="pw")
        OneTimeToken.objects.create(
            purpose="welcome",
            user=user,
            token_hash="a" * 64,
            expires_at="2099-01-01",
        )
        with pytest.raises(IntegrityError):
            OneTimeToken.objects.create(
                purpose="welcome",
                user=user,
                token_hash="a" * 64,
                expires_at="2099-01-01",
            )

    def test_indexes_exist(self):
        index_names = [idx.name for idx in OneTimeToken._meta.indexes]
        assert "mail_token_purpose_user_club" in index_names


@pytest.mark.django_db
class TestEmailPreference:
    def test_unique_constraint(self):
        club = Club.objects.create(name="Test", slug="test")
        user = User.objects.create_user("user@example.com", password="pw")
        membership = Membership.objects.create(user=user, club=club)
        EmailPreference.objects.create(membership=membership, kind="reminder", enabled=True)
        with pytest.raises(IntegrityError):
            EmailPreference.objects.create(membership=membership, kind="reminder", enabled=False)


@pytest.mark.django_db
class TestClubMailSettings:
    def test_default_reminder_days(self):
        club = Club.objects.create(name="Test", slug="test")
        settings = ClubMailSettings.objects.create(club=club)
        assert settings.reminder_days == [3]

    def test_one_to_one_with_club(self):
        club = Club.objects.create(name="Test", slug="test")
        settings = ClubMailSettings.objects.create(club=club, contact_email="contact@test.com")
        assert club.mail_settings == settings


@pytest.mark.django_db
class TestNoticeSent:
    def test_unique_constraint(self):
        user = User.objects.create_user("user@example.com", password="pw")
        NoticeSent.objects.create(kind="reminder", key="session-1", user=user)
        with pytest.raises(IntegrityError):
            NoticeSent.objects.create(kind="reminder", key="session-1", user=user)


@pytest.mark.django_db
class TestJobRun:
    def test_unique_name(self):
        JobRun.objects.create(name="test_job")
        with pytest.raises(IntegrityError):
            JobRun.objects.create(name="test_job")