"""Tests for PasswordHistory admin."""

import pytest
from django.urls import reverse

from accounts.models import PasswordHistory, User


@pytest.mark.django_db
def test_passwordhistory_admin_changelist_and_change(site_admin, login):
    """PasswordHistory changelist loads; change form returns 403 for add."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:accounts_passwordhistory_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    user = User.objects.create_user("test@example.com", password="oldpass123!")
    pwd = PasswordHistory.objects.create(user=user, password_hash="hash123")
    url = reverse("admin:accounts_passwordhistory_change", args=[pwd.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_passwordhistory_admin_no_add(site_admin, login):
    """PasswordHistory admin has no add permission."""
    client = login(site_admin)
    url = reverse("admin:accounts_passwordhistory_add")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_passwordhistory_admin_change_readonly(site_admin, login):
    """PasswordHistory admin change view is read-only (no save buttons)."""
    client = login(site_admin)
    user = User.objects.create_user("test@example.com", password="oldpass123!")
    pwd = PasswordHistory.objects.create(user=user, password_hash="hash123")
    url = reverse("admin:accounts_passwordhistory_change", args=[pwd.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should not have save buttons
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert 'name="_addanother"' not in content


@pytest.mark.django_db
def test_passwordhistory_admin_no_delete(site_admin, login):
    """PasswordHistory admin has no delete permission."""
    client = login(site_admin)
    user = User.objects.create_user("test@example.com", password="oldpass123!")
    pwd = PasswordHistory.objects.create(user=user, password_hash="hash123")
    url = reverse("admin:accounts_passwordhistory_delete", args=[pwd.pk])
    response = client.post(url)
    assert response.status_code == 403


def test_every_accounts_model_is_in_the_admin():
    """New accounts models must be registered, or named here with a reason."""
    from django.apps import apps
    from django.contrib import admin as django_admin

    left_out_on_purpose = set()
    registered = {m.__name__ for m in django_admin.site._registry}
    missing = (
        {m.__name__ for m in apps.get_app_config("accounts").get_models()}
        - registered
        - left_out_on_purpose
    )
    assert not missing, f"Register these accounts models in accounts/admin.py: {sorted(missing)}"
