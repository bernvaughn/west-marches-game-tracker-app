"""Test items admin changelists."""

import pytest
from django.urls import reverse

from items.models import (
    ClubWeightSettings,
    ContainerOpening,
    ContainerSlot,
    ContainerSlotOption,
    Item,
    RecentItemPick,
)


@pytest.mark.django_db
def test_containerslot_admin_changelist_and_change(site_admin, login, club, item):
    """ContainerSlot changelist loads and change form works."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Test Container", is_container=True)
    slot = ContainerSlot.objects.create(container=container, position=0, chance_pct=50)

    # Changelist
    url = reverse("admin:items_containerslot_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Change form
    url = reverse("admin:items_containerslot_change", args=[slot.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_containerslotoption_admin_changelist_and_change(site_admin, login, club, item):
    """ContainerSlotOption changelist loads and change form works."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Test Container", is_container=True)
    slot = ContainerSlot.objects.create(container=container, position=0, chance_pct=50)
    option = ContainerSlotOption.objects.create(
        slot=slot, item=item, qty_min=1, qty_max=2, weight=3
    )

    # Changelist
    url = reverse("admin:items_containerslotoption_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Change form
    url = reverse("admin:items_containerslotoption_change", args=[option.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_recentitempick_admin_changelist_and_change(
    site_admin, login, club, player, character, item
):
    """RecentItemPick changelist loads and change form works (read-only)."""
    from accounts.models import Membership

    client = login(site_admin)
    membership = Membership.objects.get(user=player, club=club)
    pick = RecentItemPick.objects.create(membership=membership, item=item)

    # Changelist
    url = reverse("admin:items_recentitempick_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Change form
    url = reverse("admin:items_recentitempick_change", args=[pick.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_recentitempick_admin_no_add(site_admin, login):
    """RecentItemPick admin has no add permission."""
    client = login(site_admin)
    url = reverse("admin:items_recentitempick_add")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_recentitempick_admin_change_readonly(site_admin, login, club, player, character, item):
    """RecentItemPick admin change view is read-only (no save buttons)."""
    from accounts.models import Membership

    client = login(site_admin)
    membership = Membership.objects.get(user=player, club=club)
    pick = RecentItemPick.objects.create(membership=membership, item=item)
    url = reverse("admin:items_recentitempick_change", args=[pick.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should not have save buttons
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert 'name="_addanother"' not in content


@pytest.mark.django_db
def test_recentitempick_admin_no_delete(site_admin, login, club, player, character, item):
    """RecentItemPick admin has no delete permission."""
    from accounts.models import Membership

    client = login(site_admin)
    membership = Membership.objects.get(user=player, club=club)
    pick = RecentItemPick.objects.create(membership=membership, item=item)
    url = reverse("admin:items_recentitempick_delete", args=[pick.pk])
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_clubweightsettings_admin_changelist_and_change(site_admin, login, club):
    """ClubWeightSettings changelist loads, change form works, and POST edit works."""
    client = login(site_admin)
    settings, _ = ClubWeightSettings.objects.get_or_create(club=club)

    # Changelist
    url = reverse("admin:items_clubweightsettings_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Change form GET
    url = reverse("admin:items_clubweightsettings_change", args=[settings.pk])
    response = client.get(url)
    assert response.status_code == 200

    # POST edit
    data = {"club": club.pk, "count_coin_weight": "on"}
    response = client.post(url, data)
    assert response.status_code == 302
    settings.refresh_from_db()
    assert settings.count_coin_weight is True


@pytest.mark.django_db
def test_containeropening_admin_changelist_and_change(
    site_admin, login, club, player, character, item
):
    """ContainerOpening changelist loads and change form works (read-only)."""
    from ledger.models import LedgerEntry

    client = login(site_admin)
    entry = LedgerEntry.objects.create(club=club, character=character, kind=LedgerEntry.Kind.OPENED)
    opening = ContainerOpening.objects.create(entry=entry, container=item, character=character)

    # Changelist
    url = reverse("admin:items_containeropening_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Change form
    url = reverse("admin:items_containeropening_change", args=[opening.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_containeropening_admin_no_add(site_admin, login):
    """ContainerOpening admin has no add permission."""
    client = login(site_admin)
    url = reverse("admin:items_containeropening_add")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_containeropening_admin_change_readonly(site_admin, login, club, player, character, item):
    """ContainerOpening admin change view is read-only (no save buttons)."""
    from ledger.models import LedgerEntry

    client = login(site_admin)
    entry = LedgerEntry.objects.create(club=club, character=character, kind=LedgerEntry.Kind.OPENED)
    opening = ContainerOpening.objects.create(entry=entry, container=item, character=character)
    url = reverse("admin:items_containeropening_change", args=[opening.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should not have save buttons
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert 'name="_addanother"' not in content


@pytest.mark.django_db
def test_containeropening_admin_no_delete(site_admin, login, club, player, character, item):
    """ContainerOpening admin has no delete permission."""
    from ledger.models import LedgerEntry

    client = login(site_admin)
    entry = LedgerEntry.objects.create(club=club, character=character, kind=LedgerEntry.Kind.OPENED)
    opening = ContainerOpening.objects.create(entry=entry, container=item, character=character)
    url = reverse("admin:items_containeropening_delete", args=[opening.pk])
    response = client.post(url)
    assert response.status_code == 403
