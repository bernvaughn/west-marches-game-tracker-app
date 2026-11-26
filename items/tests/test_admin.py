"""Test items admin changelists."""

import pytest
from django.contrib.admin.widgets import ForeignKeyRawIdWidget
from django.urls import reverse

from accounts.models import Club
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


@pytest.mark.django_db
def test_containerslot_admin_list_display_content(site_admin, login, club):
    """ContainerSlot changelist shows container, position, chance_pct, unknown."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Backpack", is_container=True)
    ContainerSlot.objects.create(container=container, position=3, chance_pct=42, unknown=True)

    url = reverse("admin:items_containerslot_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Backpack" in content  # container
    assert "3" in content  # position
    assert "42" in content  # chance_pct


@pytest.mark.django_db
def test_containerslot_admin_list_filter_club(site_admin, login, club):
    """ContainerSlot changelist filters by club via container__club."""
    client = login(site_admin)
    club_b = Club.objects.create(name="Club B", slug="club-b")
    container_a = Item.objects.create(club=club, name="Backpack", is_container=True)
    container_b = Item.objects.create(club=club_b, name="Sack", is_container=True)
    ContainerSlot.objects.create(container=container_a, position=0, chance_pct=50)
    ContainerSlot.objects.create(container=container_b, position=0, chance_pct=50)

    url = reverse("admin:items_containerslot_changelist")
    response = client.get(url)
    assert response.status_code == 200
    field_paths = [spec.field_path for spec in response.context["cl"].filter_specs]
    assert "container__club" in field_paths


@pytest.mark.django_db
def test_containerslot_admin_search(site_admin, login, club):
    """ContainerSlot changelist search filters on container__name."""
    client = login(site_admin)
    alpha = Item.objects.create(club=club, name="Alpha Container", is_container=True)
    beta = Item.objects.create(club=club, name="Beta Container", is_container=True)
    ContainerSlot.objects.create(container=alpha, position=0, chance_pct=50)
    ContainerSlot.objects.create(container=beta, position=0, chance_pct=50)

    url = reverse("admin:items_containerslot_changelist")
    response = client.get(url, {"q": "Alpha"})
    assert response.status_code == 200
    assert response.context["cl"].result_count == 1
    content = response.content.decode()
    assert "Alpha Container" in content
    assert "Beta Container" not in content


@pytest.mark.django_db
def test_containerslot_admin_autocomplete_container(site_admin, login, club):
    """ContainerSlot admin autocomplete works for the container FK."""
    client = login(site_admin)
    Item.objects.create(club=club, name="Backpack", is_container=True)
    url = reverse("admin:autocomplete")
    response = client.get(
        url,
        {
            "app_label": "items",
            "model_name": "containerslot",
            "field_name": "container",
            "value": "pack",
        },
    )
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_containerslot_admin_date_hierarchy(site_admin, login, club):
    """ContainerSlot changelist date_hierarchy is container__club__created and works."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Backpack", is_container=True)
    ContainerSlot.objects.create(container=container, position=0, chance_pct=50)

    url = reverse("admin:items_containerslot_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["cl"].date_hierarchy == "container__club__created"


@pytest.mark.django_db
def test_containerslot_admin_ordering(site_admin, login, club):
    """ContainerSlot changelist defaults to ordering by container, position."""
    client = login(site_admin)
    container_a = Item.objects.create(club=club, name="Alpha Box", is_container=True)
    container_b = Item.objects.create(club=club, name="Beta Box", is_container=True)
    ContainerSlot.objects.create(container=container_b, position=0, chance_pct=50)
    ContainerSlot.objects.create(container=container_a, position=5, chance_pct=50)
    ContainerSlot.objects.create(container=container_a, position=2, chance_pct=50)

    url = reverse("admin:items_containerslot_changelist")
    response = client.get(url)
    assert response.status_code == 200
    rows = response.context["cl"].result_list
    order = [(row.container_id, row.position) for row in rows]
    assert order == [
        (container_a.pk, 2),
        (container_a.pk, 5),
        (container_b.pk, 0),
    ]


@pytest.mark.django_db
def test_containerslotoption_admin_list_display_content(site_admin, login, club, item):
    """ContainerSlotOption changelist shows slot, item, qty_min, qty_max, weight."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Backpack", is_container=True)
    slot = ContainerSlot.objects.create(container=container, position=0, chance_pct=50)
    ContainerSlotOption.objects.create(slot=slot, item=item, qty_min=1, qty_max=2, weight=3)

    url = reverse("admin:items_containerslotoption_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert item.name in content  # item
    assert "1" in content  # qty_min
    assert "2" in content  # qty_max
    assert "3" in content  # weight


@pytest.mark.django_db
def test_containerslotoption_admin_list_filter_club(site_admin, login, club, item):
    """ContainerSlotOption changelist filters by club via slot__container__club."""
    client = login(site_admin)
    club_b = Club.objects.create(name="Club B", slug="club-b")
    container_a = Item.objects.create(club=club, name="Backpack", is_container=True)
    container_b = Item.objects.create(club=club_b, name="Sack", is_container=True)
    slot_a = ContainerSlot.objects.create(container=container_a, position=0, chance_pct=50)
    slot_b = ContainerSlot.objects.create(container=container_b, position=0, chance_pct=50)
    ContainerSlotOption.objects.create(slot=slot_a, item=item, qty_min=1, qty_max=2, weight=3)
    ContainerSlotOption.objects.create(slot=slot_b, item=item, qty_min=1, qty_max=2, weight=3)

    url = reverse("admin:items_containerslotoption_changelist")
    response = client.get(url)
    assert response.status_code == 200
    field_paths = [spec.field_path for spec in response.context["cl"].filter_specs]
    assert "slot__container__club" in field_paths


@pytest.mark.django_db
def test_containerslotoption_admin_search(site_admin, login, club):
    """ContainerSlotOption changelist search filters on item__name."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Backpack", is_container=True)
    slot = ContainerSlot.objects.create(container=container, position=0, chance_pct=50)
    alpha_item = Item.objects.create(club=club, name="Alpha Item", value_cp=10)
    beta_item = Item.objects.create(club=club, name="Beta Item", value_cp=10)
    ContainerSlotOption.objects.create(slot=slot, item=alpha_item, qty_min=1, qty_max=2, weight=3)
    ContainerSlotOption.objects.create(slot=slot, item=beta_item, qty_min=1, qty_max=2, weight=3)

    url = reverse("admin:items_containerslotoption_changelist")
    response = client.get(url, {"q": "Alpha"})
    assert response.status_code == 200
    assert response.context["cl"].result_count == 1
    content = response.content.decode()
    assert "Alpha Item" in content
    assert "Beta Item" not in content


@pytest.mark.django_db
def test_containerslotoption_admin_autocomplete_slot(site_admin, login, club):
    """ContainerSlotOption admin autocomplete works for the slot FK."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Backpack", is_container=True)
    ContainerSlot.objects.create(container=container, position=0, chance_pct=50)
    url = reverse("admin:autocomplete")
    response = client.get(
        url,
        {
            "app_label": "items",
            "model_name": "containerslotoption",
            "field_name": "slot",
            "value": "",
        },
    )
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_containerslotoption_admin_autocomplete_item(site_admin, login, club):
    """ContainerSlotOption admin autocomplete works for the item FK."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Backpack", is_container=True)
    ContainerSlot.objects.create(container=container, position=0, chance_pct=50)
    Item.objects.create(club=club, name="Rope", value_cp=10)
    url = reverse("admin:autocomplete")
    response = client.get(
        url,
        {
            "app_label": "items",
            "model_name": "containerslotoption",
            "field_name": "item",
            "value": "rope",
        },
    )
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_containerslotoption_admin_date_hierarchy(site_admin, login, club, item):
    """ContainerSlotOption changelist date_hierarchy is slot__container__club__created and works."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Backpack", is_container=True)
    slot = ContainerSlot.objects.create(container=container, position=0, chance_pct=50)
    ContainerSlotOption.objects.create(slot=slot, item=item, qty_min=1, qty_max=2, weight=3)

    url = reverse("admin:items_containerslotoption_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["cl"].date_hierarchy == "slot__container__club__created"


@pytest.mark.django_db
def test_containerslotoption_admin_ordering(site_admin, login, club, item):
    """ContainerSlotOption changelist defaults to ordering by slot, id."""
    client = login(site_admin)
    container = Item.objects.create(club=club, name="Box", is_container=True)
    slot = ContainerSlot.objects.create(container=container, position=0, chance_pct=50)
    ContainerSlotOption.objects.create(slot=slot, item=item, qty_min=1, qty_max=2, weight=1)
    ContainerSlotOption.objects.create(slot=slot, item=item, qty_min=1, qty_max=2, weight=9)

    url = reverse("admin:items_containerslotoption_changelist")
    response = client.get(url)
    assert response.status_code == 200
    rows = response.context["cl"].result_list
    weights = [row.weight for row in rows]
    assert weights == [1, 9]


@pytest.mark.django_db
def test_clubweightsettings_admin_list_display_content(site_admin, login, club):
    """ClubWeightSettings changelist shows club and count_coin_weight."""
    client = login(site_admin)
    ClubWeightSettings.objects.get_or_create(club=club)

    url = reverse("admin:items_clubweightsettings_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert club.name in response.content.decode()


@pytest.mark.django_db
def test_clubweightsettings_admin_search(site_admin, login, club):
    """ClubWeightSettings changelist search filters on club__name."""
    client = login(site_admin)
    other = Club.objects.create(name="Other Club", slug="other-club")
    ClubWeightSettings.objects.get_or_create(club=club)
    ClubWeightSettings.objects.get_or_create(club=other)

    url = reverse("admin:items_clubweightsettings_changelist")
    response = client.get(url, {"q": club.name})
    assert response.status_code == 200
    assert response.context["cl"].result_count == 1
    content = response.content.decode()
    assert club.name in content
    assert "Other Club" not in content


@pytest.mark.django_db
def test_clubweightsettings_admin_raw_id_club(site_admin, login, club):
    """ClubWeightSettings admin uses a raw_id widget for the club FK."""
    client = login(site_admin)
    settings, _ = ClubWeightSettings.objects.get_or_create(club=club)

    url = reverse("admin:items_clubweightsettings_change", args=[settings.pk])
    response = client.get(url)
    assert response.status_code == 200
    form = response.context["adminform"].form
    assert isinstance(form.fields["club"].widget, ForeignKeyRawIdWidget)


@pytest.mark.django_db
def test_clubweightsettings_admin_date_hierarchy(site_admin, login, club):
    """ClubWeightSettings changelist date_hierarchy is club__created and works."""
    client = login(site_admin)
    ClubWeightSettings.objects.get_or_create(club=club)

    url = reverse("admin:items_clubweightsettings_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["cl"].date_hierarchy == "club__created"


@pytest.mark.django_db
def test_clubweightsettings_admin_ordering(site_admin, login, club):
    """ClubWeightSettings changelist defaults to ordering by club__name."""
    client = login(site_admin)
    beta_club = Club.objects.create(name="Beta Club", slug="beta-club")
    alpha_club = Club.objects.create(name="Alpha Club", slug="alpha-club")
    ClubWeightSettings.objects.get_or_create(club=beta_club)
    ClubWeightSettings.objects.get_or_create(club=alpha_club)

    url = reverse("admin:items_clubweightsettings_changelist")
    response = client.get(url)
    assert response.status_code == 200
    rows = response.context["cl"].result_list
    names = [row.club.name for row in rows]
    assert names == ["Alpha Club", "Beta Club"]
