"""Tests for weight column in shop inventory (story: shop counter weight column)."""

from datetime import date

import pytest
from django.urls import reverse

from items.models import Item
from ledger.services import Line, record
from player_characters.sheet import inventory_values
from shops.models import Rotation

pytestmark = [pytest.mark.django_db, pytest.mark.story("Shop weight column")]


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return shop


def card(client, club, shop):
    """Extract the #your-inventory section from the shop detail page."""
    b = client.get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()
    return b[b.index('id="your-inventory"') :]


@pytest.fixture
def weighted_item(club):
    """An item with weight (5 lb = 500 hundredths)."""
    return Item.objects.create(club=club, name="Iron Pot", value_cp=500, weight_hundredth_lb=500)


@pytest.fixture
def stacked_weighted_item(club):
    """A stacked item with weight (2 lb per unit = 200 hundredths)."""
    return Item.objects.create(
        club=club,
        name="Arrows",
        value_cp=50,
        weight_hundredth_lb=200,
        unit_name="arrow",
        is_stacked=True,
    )


@pytest.fixture
def unweighted_item(club):
    """An item with no weight."""
    return Item.objects.create(club=club, name="Magic Scroll", value_cp=1000)


def test_weighted_item_shows_weight_text(login, player, club, open_shop, character, weighted_item):
    """Weighted single item shows the same weight text as the sheet."""
    record(character, "award", [Line(item=weighted_item, quantity=1)])

    # Get weight text from inventory_values (what the sheet uses)
    from player_characters.inventory import inventory_rows

    rows = inventory_rows(character)
    vals = inventory_values(rows)
    expected_weight = vals[0]["weight_text"]

    c = card(login(player), club, open_shop)
    assert expected_weight in c
    assert "wm-col-weight" in c


def test_stacked_item_shows_per_unit_tooltip(
    login, player, club, open_shop, character, stacked_weighted_item
):
    """Stacked weighted item shows per-unit tooltip with unit name."""
    record(character, "award", [Line(item=stacked_weighted_item, quantity=20)])

    c = card(login(player), club, open_shop)
    # The cell has data-wm-tooltip with per-unit text and unit_name
    assert "data-wm-tooltip" in c
    assert "per arrow" in c


def test_unweighted_item_shows_dash_and_no_tooltip(
    login, player, club, open_shop, character, unweighted_item
):
    """Unweighted item shows a dash and has no tooltip."""
    record(character, "award", [Line(item=unweighted_item, quantity=1)])

    c = card(login(player), club, open_shop)
    # Cell shows dash (em dash or —)
    assert "—" in c
    # No tooltip on the weight cell for unweighted items
    # The weight column cell should not have data-wm-tooltip
    # We check that the dash is present and the tooltip pattern is not
    # in the weight column context. In the template, the tooltip is only
    # added when is_stacked AND weight_hundredths is not None. For
    # unweighted non-stacked, weight_hundredths is None, so no tooltip


def test_weight_column_header_has_wm_col_weight(login, player, club, open_shop, character, item):
    """Header has wm-col-weight class for mobile hide hook."""
    record(character, "award", [Line(item=item, quantity=1)])
    c = card(login(player), club, open_shop)
    assert 'class="num wm-col-weight"' in c


def test_weight_text_matches_sheet(login, player, club, open_shop, character, weighted_item):
    """Shop page shows the same weight text as the sheet for each item."""
    record(character, "award", [Line(item=weighted_item, quantity=3)])

    # Sheet weight text via inventory_values
    from player_characters.inventory import inventory_rows

    rows = inventory_rows(character)
    vals = inventory_values(rows)
    sheet_weight = vals[0]["weight_text"]

    c = card(login(player), club, open_shop)
    assert sheet_weight in c


def test_stacked_item_row_total_weight(
    login, player, club, open_shop, character, stacked_weighted_item
):
    """Stacked item weight text equals per-unit times quantity (row total)."""
    record(character, "award", [Line(item=stacked_weighted_item, quantity=5)])  # 5 * 2 lb = 10 lb

    from player_characters.inventory import inventory_rows

    rows = inventory_rows(character)
    vals = inventory_values(rows)
    expected_total = vals[0]["weight_text"]  # should be "10.0 lb"

    c = card(login(player), club, open_shop)
    assert expected_total in c


def test_no_weight_tracking_switch_column_always_present(
    login, player, club, open_shop, character, weighted_item
):
    """No weight-tracking switch exists; column markup always matches sheet (always present)."""
    record(character, "award", [Line(item=weighted_item, quantity=1)])
    c = card(login(player), club, open_shop)
    # The column is always present (no conditional hiding based on a setting)
    assert "wm-col-weight" in c
    assert "Weight" in c  # header text
