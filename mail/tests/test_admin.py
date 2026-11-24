"""Test mail admin changelists."""

import pytest
from django.urls import reverse

from mail.models import ClubMailSettings, DoNotEmail, EmailMessage, JobRun


@pytest.mark.django_db
def test_emailmessage_admin_changelist(site_admin, login):
    """EmailMessage changelist loads."""
    client = login(site_admin)
    url = reverse("admin:mail_emailmessage_changelist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_donotemail_admin_changelist(site_admin, login):
    """DoNotEmail changelist loads."""
    client = login(site_admin)
    url = reverse("admin:mail_donotemail_changelist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_jobrun_admin_changelist(site_admin, login):
    """JobRun changelist loads."""
    client = login(site_admin)
    url = reverse("admin:mail_jobrun_changelist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_emailmessage_admin_no_add(site_admin, login):
    """EmailMessage admin has no add permission."""
    client = login(site_admin)
    url = reverse("admin:mail_emailmessage_add")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_donotemail_admin_no_add(site_admin, login):
    """DoNotEmail admin has no add permission."""
    client = login(site_admin)
    url = reverse("admin:mail_donotemail_add")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_jobrun_admin_no_add(site_admin, login):
    """JobRun admin has no add permission."""
    client = login(site_admin)
    url = reverse("admin:mail_jobrun_add")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_emailmessage_admin_change_readonly(site_admin, login):
    """EmailMessage admin change view is read-only (no save buttons)."""
    client = login(site_admin)
    msg = EmailMessage.objects.create(
        kind=EmailMessage.Kind.WELCOME,
        to_address="test@example.com",
        subject="Test",
        status=EmailMessage.Status.QUEUED,
    )
    url = reverse("admin:mail_emailmessage_change", args=[msg.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should not have save buttons
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert 'name="_addanother"' not in content


@pytest.mark.django_db
def test_donotemail_admin_change_readonly(site_admin, login):
    """DoNotEmail admin change view is read-only."""
    client = login(site_admin)
    dne = DoNotEmail.objects.create(address="test@example.com", reason=DoNotEmail.Reason.MANUAL)
    url = reverse("admin:mail_donotemail_change", args=[dne.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert 'name="_addanother"' not in content


@pytest.mark.django_db
def test_jobrun_admin_change_readonly(site_admin, login):
    """JobRun admin change view is read-only."""
    client = login(site_admin)
    jr = JobRun.objects.create(name="test_job")
    url = reverse("admin:mail_jobrun_change", args=[jr.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert 'name="_addanother"' not in content


@pytest.mark.django_db
def test_emailmessage_admin_no_delete(site_admin, login):
    """EmailMessage admin has no delete permission."""
    client = login(site_admin)
    msg = EmailMessage.objects.create(
        kind=EmailMessage.Kind.WELCOME,
        to_address="test@example.com",
        subject="Test",
        status=EmailMessage.Status.QUEUED,
    )
    url = reverse("admin:mail_emailmessage_delete", args=[msg.pk])
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_donotemail_admin_no_delete(site_admin, login):
    """DoNotEmail admin has no delete permission."""
    client = login(site_admin)
    dne = DoNotEmail.objects.create(address="test@example.com", reason=DoNotEmail.Reason.MANUAL)
    url = reverse("admin:mail_donotemail_delete", args=[dne.pk])
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_jobrun_admin_no_delete(site_admin, login):
    """JobRun admin has no delete permission."""
    client = login(site_admin)
    jr = JobRun.objects.create(name="test_job")
    url = reverse("admin:mail_jobrun_delete", args=[jr.pk])
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_emailmessage_admin_list_display(site_admin, login):
    """EmailMessage admin shows correct fields."""
    client = login(site_admin)
    EmailMessage.objects.create(
        kind=EmailMessage.Kind.WELCOME,
        to_address="test@example.com",
        subject="Test",
        status=EmailMessage.Status.QUEUED,
        attempts=1,
        last_error="Some error",
    )
    url = reverse("admin:mail_emailmessage_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "test@example.com" in content
    assert "welcome" in content
    assert "queued" in content
    assert "Some error" in content


@pytest.mark.django_db
def test_donotemail_admin_list_display(site_admin, login):
    """DoNotEmail admin shows correct fields."""
    client = login(site_admin)
    DoNotEmail.objects.create(address="blocked@example.com", reason=DoNotEmail.Reason.BOUNCE)
    url = reverse("admin:mail_donotemail_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "blocked@example.com" in content
    assert "bounce" in content


@pytest.mark.django_db
def test_jobrun_admin_list_display(site_admin, login):
    """JobRun admin shows correct fields including timer_running."""
    client = login(site_admin)
    from django.utils import timezone

    JobRun.objects.create(name="test_job", last_run_at=timezone.now(), ok=True, note="test note")
    url = reverse("admin:mail_jobrun_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "test_job" in content
    assert "test note" in content
    # Timer should show "Running" since last_run_at is now
    assert "Running" in content


@pytest.mark.django_db
def test_jobrun_timer_stopped(site_admin, login):
    """JobRun timer shows Stopped when last_run_at is old."""
    client = login(site_admin)
    from datetime import timedelta

    from django.utils import timezone

    old_time = timezone.now() - timedelta(hours=1)
    JobRun.objects.create(name="old_job", last_run_at=old_time, ok=True)
    url = reverse("admin:mail_jobrun_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Stopped" in content


@pytest.mark.django_db
def test_jobrun_timer_never(site_admin, login):
    """JobRun timer shows Never when last_run_at is None."""
    client = login(site_admin)
    JobRun.objects.create(name="never_job", last_run_at=None, ok=True)
    url = reverse("admin:mail_jobrun_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Never" in content


@pytest.mark.django_db
def test_clubmailsettings_admin_changelist_and_change_form(site_admin, login, club):
    """ClubMailSettings (where the club contact email lives) is in the admin and editable."""
    settings, _ = ClubMailSettings.objects.get_or_create(club=club)
    settings.contact_email = "club@example.com"
    settings.save()
    client = login(site_admin)

    response = client.get(reverse("admin:mail_clubmailsettings_changelist"))
    assert response.status_code == 200
    assert b"club@example.com" in response.content

    url = reverse("admin:mail_clubmailsettings_change", args=[settings.pk])
    assert client.get(url).status_code == 200
    data = {"club": club.pk, "contact_email": "new@example.com", "reminder_days": "[1, 3]"}
    assert client.post(url, data).status_code == 302
    settings.refresh_from_db()
    assert settings.contact_email == "new@example.com"
