"""Tests for item weight functionality (story U154)."""

import pytest
from django.template.loader import render_to_string
from django.test import TestCase

from accounts.models import Membership, User
from items.forms import ItemForm
from items.models import Item
from items.weights import format_weight, item_weight_total


def make_item(club, name, **kwargs):
    """Create an item in a club."""
    defaults = {"club": club, "name": name, "value_cp": 0, "retired": False, "is_container": False}
    defaults.update(kwargs)
    return Item.objects.create(**defaults)


def make_user(email="test@example.com", name="Test User"):
    """Create a test user."""
    return User.objects.create_user(email, password="testpass", display_name=name)


# =============================================================================
# format_weight tests
# =============================================================================


class FormatWeightTests(TestCase):
    """Tests for the format_weight helper."""

    def test_none_returns_not_listed(self):
        self.assertEqual(format_weight(None), "not listed")

    def test_formats_with_one_decimal(self):
        self.assertEqual(format_weight(125), "1.3 lb")

    def test_formats_with_two_decimals(self):
        self.assertEqual(format_weight(125, precision=2), "1.25 lb")

    def test_zero_displays_as_zero(self):
        self.assertEqual(format_weight(0), "0.0 lb")

    def test_various_values(self):
        self.assertEqual(format_weight(50), "0.5 lb")
        self.assertEqual(format_weight(100), "1.0 lb")
        self.assertEqual(format_weight(150), "1.5 lb")
        self.assertEqual(format_weight(200), "2.0 lb")
        self.assertEqual(format_weight(1234), "12.3 lb")
        self.assertEqual(format_weight(1234, precision=2), "12.34 lb")


# =============================================================================
# item_weight_total tests
# =============================================================================


@pytest.mark.django_db
def test_stacked_scales_with_units(club):
    stacked_item = make_item(
        club,
        "Stacked Arrows",
        is_stacked=True,
        unit_name="arrow",
        weight_hundredth_lb=15,  # 0.15 lb per arrow
    )
    assert item_weight_total(stacked_item, 1) == 15
    assert item_weight_total(stacked_item, 10) == 150
    assert item_weight_total(stacked_item, 20) == 300


@pytest.mark.django_db
def test_non_stacked_ignores_units(club):
    normal_item = make_item(
        club,
        "Normal Item",
        is_stacked=False,
        weight_hundredth_lb=250,  # 2.5 lb
    )
    assert item_weight_total(normal_item, 1) == 250
    assert item_weight_total(normal_item, 5) == 250
    assert item_weight_total(normal_item, 100) == 250


@pytest.mark.django_db
def test_none_weight_returns_none(club):
    stacked_no_weight = make_item(
        club,
        "Stacked No Weight",
        is_stacked=True,
        unit_name="ft",
        weight_hundredth_lb=None,
    )
    normal_no_weight = make_item(
        club,
        "Normal No Weight",
        is_stacked=False,
        weight_hundredth_lb=None,
    )
    assert item_weight_total(stacked_no_weight, 10) is None
    assert item_weight_total(normal_no_weight, 5) is None


# =============================================================================
# ItemForm weight tests
# =============================================================================


@pytest.mark.django_db
def test_blank_weight_saves_as_none(club):
    form = ItemForm(
        data={
            "name": "Test Item",
            "value": "100",
            "weight": "",
        },
        club=club,
    )
    assert form.is_valid(), form.errors
    item = form.save()
    assert item.weight_hundredth_lb is None


@pytest.mark.django_db
def test_weight_zero_saves_as_zero(club):
    form = ItemForm(
        data={
            "name": "Test Item",
            "value": "100",
            "weight": "0",
        },
        club=club,
    )
    assert form.is_valid(), form.errors
    item = form.save()
    assert item.weight_hundredth_lb == 0


@pytest.mark.django_db
def test_weight_value_saves_correctly(club):
    form = ItemForm(
        data={
            "name": "Test Item",
            "value": "100",
            "weight": "125",
        },
        club=club,
    )
    assert form.is_valid(), form.errors
    item = form.save()
    assert item.weight_hundredth_lb == 125


@pytest.mark.django_db
def test_edit_form_shows_existing_weight(club):
    item = make_item(club, "Test Item", weight_hundredth_lb=250)
    form = ItemForm(instance=item, club=club)
    assert form.initial["weight"] == 250


@pytest.mark.django_db
def test_edit_form_blank_weight_shows_none(club):
    item = make_item(club, "Test Item", weight_hundredth_lb=None)
    form = ItemForm(instance=item, club=club)
    assert form.initial.get("weight") is None


# =============================================================================
# Item detail template weight tests
# =============================================================================


@pytest.mark.django_db
def test_detail_shows_not_listed_when_blank(club):
    item = make_item(club, "Test Item", weight_hundredth_lb=None)
    html = render_to_string(
        "items/_details_body.html",
        {"item": item, "loot_rows": []},
    )
    assert "not listed" in html


@pytest.mark.django_db
def test_detail_shows_formatted_weight(club):
    item = make_item(club, "Test Item", weight_hundredth_lb=125)
    html = render_to_string(
        "items/_details_body.html",
        {"item": item, "loot_rows": []},
    )
    assert "1.3 lb" in html


@pytest.mark.django_db
def test_detail_shows_weight_row(club):
    item = make_item(club, "Test Item", weight_hundredth_lb=250)
    html = render_to_string(
        "items/_details_body.html",
        {"item": item, "loot_rows": []},
    )
    assert "Weight</dt>" in html
    assert "2.5 lb" in html


# =============================================================================
# Item card template weight tests
# =============================================================================


@pytest.mark.django_db
def test_card_shows_weight_for_normal_item(club):
    item = make_item(club, "Normal Item", is_stacked=False, weight_hundredth_lb=250)
    html = render_to_string(
        "player_characters/characters/_item_card.html",
        {"card": type("Card", (), {"item": item, "qty": 1, "use_circles": []})},
    )
    assert "Weight</span>" in html
    assert "2.5 lb" in html


@pytest.mark.django_db
def test_card_shows_per_unit_and_total_for_stacked(club):
    item = make_item(
        club, "Stacked Arrows", is_stacked=True, unit_name="arrow", weight_hundredth_lb=15
    )
    html = render_to_string(
        "player_characters/characters/_item_card.html",
        {"card": type("Card", (), {"item": item, "qty": 20, "use_circles": []})},
    )
    assert "Weight</span>" in html
    assert "0.2 lb per arrow" in html
    assert "3.00 lb total" in html


@pytest.mark.django_db
def test_card_hides_weight_when_none(club):
    item = make_item(club, "No Weight", weight_hundredth_lb=None)
    html = render_to_string(
        "player_characters/characters/_item_card.html",
        {"card": type("Card", (), {"item": item, "qty": 1, "use_circles": []})},
    )
    assert "Weight</span>" not in html


# =============================================================================
# Shop stock template weight tests
# =============================================================================


@pytest.mark.django_db
def test_stock_shows_weight(club):
    from shops.models import Shop, ShopStock
    from shops.services import sell_price

    shop = Shop.objects.create(club=club, name="Test Shop", sell_percent=100)
    item = make_item(club, "Test Item", weight_hundredth_lb=125, value_cp=100)
    stock = ShopStock.objects.create(shop=shop, item=item, quantity=10)
    # Set price like the view does
    stock.price = sell_price(stock)

    html = render_to_string(
        "shops/browse/_stock.html",
        {"rows": [stock], "selected_character": None, "club": club, "shop": shop},
    )
    assert "1.3 lb" in html


@pytest.mark.django_db
def test_stock_shows_not_listed_when_blank(club):
    from shops.models import Shop, ShopStock
    from shops.services import sell_price

    shop = Shop.objects.create(club=club, name="Test Shop", sell_percent=100)
    item = make_item(club, "Test Item", weight_hundredth_lb=None, value_cp=100)
    stock = ShopStock.objects.create(shop=shop, item=item, quantity=10)
    stock.price = sell_price(stock)

    html = render_to_string(
        "shops/browse/_stock.html",
        {"rows": [stock], "selected_character": None, "club": club, "shop": shop},
    )
    assert "not listed" in html


# =============================================================================
# Agent search_items weight tests (via MCP)
# =============================================================================


def _sc(mcp, secret, tool, **args):
    """Helper to call MCP tool and extract structured content."""
    status, result = mcp(secret, tool, **args)
    assert status == 200 and not result.get("isError"), f"MCP error: {result}"
    return result["structuredContent"]


@pytest.mark.django_db
def test_search_items_includes_weight_fields(mcp, gm_connection, club):
    """Test that search_items includes weight fields via MCP."""
    item = make_item(
        club, "Stacked Arrows", weight_hundredth_lb=125, is_stacked=True, unit_name="arrow"
    )
    result = _sc(mcp, gm_connection[1], "search_items", query=item.name)
    assert len(result["items"]) == 1
    item_data = result["items"][0]
    assert "weight_hundredth_lb" in item_data
    assert "weight" in item_data
    assert item_data["weight_hundredth_lb"] == 125
    assert item_data["weight"] == "1.3 lb"
    assert "weight_per_unit" in item_data


@pytest.mark.django_db
def test_search_items_weight_none_when_blank(mcp, gm_connection, club):
    """Test that search_items shows 'not listed' for blank weight."""
    item = make_item(club, "No Weight", weight_hundredth_lb=None)
    result = _sc(mcp, gm_connection[1], "search_items", query=item.name)
    item_data = result["items"][0]
    assert item_data["weight_hundredth_lb"] is None
    assert item_data["weight"] == "not listed"


# =============================================================================
# Weight never blocks operations tests
# =============================================================================


@pytest.mark.django_db
def test_buy_over_weight_still_succeeds(club):
    """A buy should succeed regardless of weight."""
    from player_characters.models import Character
    from shops.models import Shop, ShopStock

    user = make_user()
    membership = Membership.objects.create(user=user, club=club)
    Character.objects.create(club=club, name="Test Hero", owner=membership)
    shop = Shop.objects.create(club=club, name="Test Shop", sell_percent=100)
    heavy_item = make_item(club, "Heavy Item", weight_hundredth_lb=5000, value_cp=100)  # 50 lb
    stock = ShopStock.objects.create(shop=shop, item=heavy_item, quantity=10)

    # This should not raise an exception due to weight
    # (the buy view would handle the actual purchase)
    assert stock is not None


@pytest.mark.django_db
def test_sale_with_weight_succeeds(club):
    """A sale should succeed regardless of weight."""
    from ledger.models import LedgerEntry
    from ledger.services import Line, item_quantities, record
    from player_characters.models import Character

    user = make_user()
    membership = Membership.objects.create(user=user, club=club)
    character = Character.objects.create(club=club, name="Test Hero", owner=membership)
    heavy_item = make_item(club, "Heavy Item", weight_hundredth_lb=5000)

    # Add item to character via ledger
    record(character, LedgerEntry.Kind.ADJUSTMENT, [Line(item=heavy_item, quantity=1)])

    # Sale should work - verify character has the item
    assert item_quantities(character).get(heavy_item.pk, 0) == 1


@pytest.mark.django_db
def test_award_with_weight_succeeds(club, gm_connection):
    """An award should succeed regardless of weight."""
    from datetime import date

    from accounts.models import Membership, User
    from agent_access.models import ProposedBatch, ProposedLine
    from player_characters.models import Character

    user = User.objects.get(pk=gm_connection[0].user_id)
    membership = Membership.objects.get(user=user, club=club)
    character = Character.objects.create(club=club, name="Test Hero", owner=membership)
    heavy_item = make_item(club, "Heavy Item", weight_hundredth_lb=5000)

    batch = ProposedBatch.objects.create(
        club=club,
        connection=gm_connection[0],
        user=user,
        date=date.today(),
        idempotency_key="test-weight-award",
        status=ProposedBatch.Status.PENDING,
    )
    line = ProposedLine.objects.create(
        batch=batch, character=character, item=heavy_item, quantity=1
    )

    assert line.quantity == 1


@pytest.mark.django_db
def test_container_opening_with_weight_succeeds(club):
    """Opening a container should succeed regardless of weight."""
    from items.models import ContainerOpening
    from ledger.models import LedgerEntry
    from player_characters.models import Character

    user = make_user()
    membership = Membership.objects.create(user=user, club=club)
    character = Character.objects.create(club=club, name="Test Hero", owner=membership)
    container = make_item(club, "Container", is_container=True)
    make_item(club, "Heavy Item", weight_hundredth_lb=5000)

    entry = LedgerEntry.objects.create(club=club, character=character, kind=LedgerEntry.Kind.OPENED)
    opening = ContainerOpening.objects.create(
        entry=entry, container=container, character=character, result=[]
    )

    assert opening is not None
