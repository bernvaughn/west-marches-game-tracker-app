"""Tests for the Consumables dashboard provider."""

import pytest
from django.test import Client
from django.urls import reverse

from accounts.dashboard_providers import (
    ConsumablesDashboardProvider,
    get_providers,
    register_provider,
)
from accounts.models import Membership
from items.magic_types import MagicType
from items.models import Item
from ledger.services import Line, record_many


@pytest.fixture
def provider():
    return ConsumablesDashboardProvider()


@pytest.fixture(autouse=True)
def register_consumables_provider():
    """Ensure the provider is registered for tests."""
    for p in get_providers():
        if p.key == "consumables":
            break
    else:
        register_provider(ConsumablesDashboardProvider())
    yield
    # Cleanup not needed for tests


class MockRequest:
    def __init__(self, club, user):
        self.club = club
        self.user = user


@pytest.mark.django_db
def test_consumables_provider_should_not_show_when_many_non_consumable(
    player, club, character, item
):
    """Provider should NOT show when character has many of a non-consumable item (3 Wolf pelts)."""
    provider = ConsumablesDashboardProvider()

    # Give character 3 of a non-consumable item (no magic type, no traits)
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=3)],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is False


@pytest.mark.django_db
def test_consumables_provider_should_show_when_magic_type_potion(player, club, character):
    """Provider should show a Healing Potion even at quantity 1."""
    provider = ConsumablesDashboardProvider()
    potion = Item.objects.create(
        club=club, name="Healing Potion", magic_type=MagicType.POTION, value_cp=50
    )

    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=potion, quantity=1)],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_consumables_provider_should_show_when_magic_type_scroll(player, club, character):
    """Provider should show a Scroll even at quantity 1."""
    provider = ConsumablesDashboardProvider()
    scroll = Item.objects.create(
        club=club, name="Scroll of Identify", magic_type=MagicType.SCROLL, value_cp=50
    )

    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=scroll, quantity=1)],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_consumables_provider_should_show_when_trait_consumable(player, club, character, item):
    """Provider should show when item has 'consumable' trait."""
    provider = ConsumablesDashboardProvider()

    # Add consumable trait to item
    item.traits = "consumable, magical"
    item.save(update_fields=["traits"])

    # Give character 1 of the item
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=1)],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_consumables_provider_should_show_when_trait_consumable_case_insensitive(
    player, club, character, item
):
    """Provider should show when item has 'Consumable' trait (case insensitive)."""
    provider = ConsumablesDashboardProvider()

    # Add Consumable trait with different case
    item.traits = "Consumable, Magical"
    item.save(update_fields=["traits"])

    # Give character 1 of the item
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=1)],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_consumables_provider_should_not_show_when_no_items(player, club, character):
    """Provider should NOT show when character has no items."""
    provider = ConsumablesDashboardProvider()

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is False


@pytest.mark.django_db
def test_consumables_provider_should_not_show_when_single_non_consumable(
    player, club, character, item
):
    """Provider should NOT show when character has 1 of a non-consumable item."""
    provider = ConsumablesDashboardProvider()

    # Give character 1 of the item (no consumable trait)
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=1)],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is False


@pytest.mark.django_db
def test_consumables_provider_get_context_includes_consumable_excludes_pelts(
    player, club, character, item
):
    """Provider context lists a Healing Potion and excludes 3 non-consumable pelts."""
    provider = ConsumablesDashboardProvider()
    potion = Item.objects.create(
        club=club, name="Healing Potion", magic_type=MagicType.POTION, value_cp=50
    )

    # 3 non-consumable pelts + 1 potion
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[
                    Line(item=item, quantity=3),
                    Line(item=potion, quantity=1),
                ],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    ctx = provider.get_context(request, club, character, membership)

    assert "consumable_items" in ctx
    assert len(ctx["consumable_items"]) == 1
    ci = ctx["consumable_items"][0]
    assert ci["item"] == potion
    assert ci["quantity"] == 1
    assert "consume_partial_url" in ci
    # Check URL format
    expected_url = reverse("accounts:consumable_consume_partial", args=[club.slug, potion.pk])
    assert ci["consume_partial_url"] == expected_url


@pytest.mark.django_db
def test_consumables_provider_get_context_excludes_non_consumables(player, club, character, item):
    """Provider context excludes non-consumable items."""
    provider = ConsumablesDashboardProvider()

    # Create a second item
    second_item = Item.objects.create(
        club=club,
        name="Potion of Healing",
        value_cp=500,
        traits="consumable",
    )

    # Give character 1 of a regular item and 2 of a consumable
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[
                    Line(item=item, quantity=1),
                    Line(item=second_item, quantity=2),
                ],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = Membership.objects.get(user=player, club=club)

    ctx = provider.get_context(request, club, character, membership)

    assert len(ctx["consumable_items"]) == 1
    assert ctx["consumable_items"][0]["item"] == second_item


@pytest.mark.django_db
def test_consumables_provider_is_consumable_method():
    """Test the _is_consumable helper method directly."""
    provider = ConsumablesDashboardProvider()

    # Create mock items
    class MockItem:
        def __init__(self, traits="", magic_type=""):
            self.traits = traits
            self.magic_type = magic_type

    # Magic type decides, quantity never does
    assert provider._is_consumable(MockItem(magic_type=MagicType.POTION)) is True
    assert provider._is_consumable(MockItem(magic_type=MagicType.POTION)) is True
    assert provider._is_consumable(MockItem(magic_type=MagicType.SCROLL)) is True

    # Traits decide, quantity never does
    assert provider._is_consumable(MockItem(traits="consumable")) is True
    assert provider._is_consumable(MockItem(traits="CONSUMABLE")) is True
    assert provider._is_consumable(MockItem(traits="Consumable")) is True
    assert provider._is_consumable(MockItem(traits="potion, consumable, magical")) is True

    # Quantity alone never decides
    assert provider._is_consumable(MockItem()) is False
    assert provider._is_consumable(MockItem()) is False
    assert provider._is_consumable(MockItem(traits="magical")) is False
    assert provider._is_consumable(MockItem(traits="magical")) is False
    assert provider._is_consumable(MockItem(None)) is False
    assert provider._is_consumable(MockItem(magic_type="weapon")) is False


@pytest.mark.django_db
def test_consumable_consume_partial_view_200_for_potion_quantity_1(player, club, character):
    """Consume view accepts a Potion even at quantity 1."""
    potion = Item.objects.create(
        club=club, name="Healing Potion", magic_type=MagicType.POTION, value_cp=50
    )
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=potion, quantity=1)],
                note="Test",
                actor=player,
            )
        ]
    )

    client = Client()
    client.force_login(player)

    url = reverse("accounts:consumable_consume_partial", args=[club.slug, potion.pk])
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    content = response.content.decode()
    assert potion.name in content


@pytest.mark.django_db
def test_consumable_consume_partial_view_returns_modal(player, club, character, item):
    """Test the consumable_consume_partial view returns modal HTML."""
    # Give character 2 of the item
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=2)],
                note="Test",
                actor=player,
            )
        ]
    )

    # Make item consumable via trait
    item.traits = "consumable"
    item.save(update_fields=["traits"])

    client = Client()
    client.force_login(player)

    url = reverse("accounts:consumable_consume_partial", args=[club.slug, item.pk])
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Consume 1" in content
    assert item.name in content
    assert "Consume" in content  # Submit button
    assert "Cancel" in content


@pytest.mark.django_db
def test_consumable_consume_partial_view_404_for_non_consumable(player, club, character, item):
    """Test the consumable_consume_partial view returns 404 for non-consumable."""
    # Give character 1 of a non-consumable item
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=1)],
                note="Test",
                actor=player,
            )
        ]
    )

    client = Client()
    client.force_login(player)

    url = reverse("accounts:consumable_consume_partial", args=[club.slug, item.pk])
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_consumable_consume_partial_view_404_for_non_consumable_even_high_qty(
    player, club, character, item
):
    """Consume view rejects non-consumables even when quantity is high."""
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=10)],
                note="Test",
                actor=player,
            )
        ]
    )

    client = Client()
    client.force_login(player)

    url = reverse("accounts:consumable_consume_partial", args=[club.slug, item.pk])
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_consumable_consume_partial_view_404_for_no_item(player, club, character, item):
    """Test the consumable_consume_partial view returns 404 when character has none."""
    client = Client()
    client.force_login(player)

    url = reverse("accounts:consumable_consume_partial", args=[club.slug, item.pk])
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 404
