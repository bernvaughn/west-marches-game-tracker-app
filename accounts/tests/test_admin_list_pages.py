"""Tests for admin list pages in accounts app."""

import pytest
from django.urls import reverse

from accounts.models import Club, Membership, Message, SiteFeedback, SiteSettings, WhitelistEntry


@pytest.mark.django_db
def test_club_admin_changelist_and_change(site_admin, login):
    """Club changelist loads and change form works."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:accounts_club_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    club = Club.objects.create(name="Test Club", slug="test-club")
    url = reverse("admin:accounts_club_change", args=[club.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_site_settings_admin_changelist_and_change(site_admin, login):
    """SiteSettings changelist loads and change form works (singleton pk=1)."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:accounts_sitesettings_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance (singleton with pk=1) and test change form
    settings = SiteSettings.load()
    settings.donate_url = "https://example.com/donate"
    settings.save()
    url = reverse("admin:accounts_sitesettings_change", args=[settings.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_whitelist_entry_admin_changelist_and_change(site_admin, club, login):
    """WhitelistEntry changelist loads and change form works."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:accounts_whitelistentry_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    entry = WhitelistEntry.objects.create(club=club, email="test@example.com")
    url = reverse("admin:accounts_whitelistentry_change", args=[entry.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_message_admin_changelist_and_change(site_admin, club, player, login):
    """Message changelist loads and change form works."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:accounts_message_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    sender = Membership.objects.get(user=player, club=club)
    message = Message.objects.create(
        club=club, sender=sender, body="Test message", kind=Message.Kind.MESSAGE
    )
    url = reverse("admin:accounts_message_change", args=[message.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_site_feedback_admin_changelist_and_change(site_admin, club, player, login):
    """SiteFeedback changelist loads and change form works."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:accounts_sitefeedback_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    feedback = SiteFeedback.objects.create(
        user=player, club=club, kind=SiteFeedback.Kind.BUG, body="Test feedback"
    )
    url = reverse("admin:accounts_sitefeedback_change", args=[feedback.pk])
    response = client.get(url)
    assert response.status_code == 200
