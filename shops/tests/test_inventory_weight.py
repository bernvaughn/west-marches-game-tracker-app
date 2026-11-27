"""Tests for the Weight column in the shop's "Your inventory" table."""

import html
import re
from datetime import date

import pytest
from django.urls import reverse

from items.models import Item
from ledger.services import Line, record
from player_characters.inventory import inventory_rows
from player_characters.sheet import inventory_values
from shops.models import Rotation

pytestmark = [pytest.mark.django_db, pytest.mark.story("Shop weight column")]

WEIGHT_TD = re.compile(r'<td class="num wm-col-weight"([^>]*)>(.*?)</td>', re.S)


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return shop


def card(client, club, shop):
    """Extract the #your-inventory section from the shop detail page."""
    b = client.get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()
    return b[b.index('id="your-inventory"') :]


def sheet_page(client, club, character):
    return client.get(reverse("characters:detail", args=[club.slug, character.pk])).content.decode()


def weight_cell(page, item_name):
    """Return (attrs, text) of the Weight <td> in the table row for ``item_name``."""
    for chunk in page.split("<tr")[1:]:
        if item_name in chunk and (m := WEIGHT_TD.search(chunk)):
            return m.group(1), html.unescape(m.group(2)).strip()
    raise AssertionError(f"no weight cell found for {item_name!r}")


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


@pytest.fixture
def unweighted_stacked_item(club):
    """A stacked item with no weight."""
    return Item.objects.create(
        club=club, name="Pebbles", value_cp=1, unit_name="pebble", is_stacked=True
    )


def test_shop_weight_cells_match_sheet(
    login,
    player,
    club,
    open_shop,
    character,
    weighted_item,
    stacked_weighted_item,
    unweighted_item,
):
    """Each item's Weight cell on the shop page equals the sheet's, text and tooltip."""
    record(
        character,
        "award",
        [
            Line(item=weighted_item, quantity=3),
            Line(item=stacked_weighted_item, quantity=5),
            Line(item=unweighted_item, quantity=1),
        ],
    )
    client = login(player)
    shop_html = card(client, club, open_shop)
    sheet_html = sheet_page(client, club, character)

    rows = inventory_rows(character)
    values = {r.item.name: v for r, v in zip(rows, inventory_values(rows), strict=True)}
    assert values["Iron Pot"]["weight_text"] == "5.0 lb"
    assert values["Arrows"]["weight_text"] == "10.0 lb"  # 5 units x 2 lb
    assert values["Magic Scroll"]["weight_text"] == "—"

    for name, v in values.items():
        shop_attrs, shop_text = weight_cell(shop_html, name)
        sheet_attrs, sheet_text = weight_cell(sheet_html, name)
        assert shop_text == sheet_text == v["weight_text"], name
        assert shop_attrs.strip() == sheet_attrs.strip(), name


def test_unweighted_item_shows_dash_and_no_tooltip(
    login, player, club, open_shop, character, unweighted_item
):
    record(character, "award", [Line(item=unweighted_item, quantity=1)])

    attrs, text = weight_cell(card(login(player), club, open_shop), "Magic Scroll")
    assert text == "—"
    assert "data-wm-tooltip" not in attrs
    assert "title" not in attrs


def test_unweighted_stacked_item_shows_dash_and_no_tooltip(
    login, player, club, open_shop, character, unweighted_stacked_item
):
    """The tooltip is guarded on a known weight, even for stacked items."""
    record(character, "award", [Line(item=unweighted_stacked_item, quantity=7)])

    attrs, text = weight_cell(card(login(player), club, open_shop), "Pebbles")
    assert text == "—"
    assert "data-wm-tooltip" not in attrs
    assert "title" not in attrs


def test_stacked_item_shows_per_unit_tooltip(
    login, player, club, open_shop, character, stacked_weighted_item
):
    record(character, "award", [Line(item=stacked_weighted_item, quantity=20)])

    (vals,) = inventory_values(inventory_rows(character))
    per_unit = vals["weight_per_unit_text"]
    assert per_unit == "2.0 lb"
    assert vals["weight_text"] == "40.0 lb"  # row total, not per unit

    attrs, text = weight_cell(card(login(player), club, open_shop), "Arrows")
    assert text == vals["weight_text"]
    assert "data-wm-tooltip" in attrs
    assert f'title="{per_unit} per arrow"' in attrs


def test_weight_header_has_hide_class(login, player, club, open_shop, character, item):
    """The header carries wm-col-weight, the hook that hides it on narrow screens."""
    record(character, "award", [Line(item=item, quantity=1)])
    c = card(login(player), club, open_shop)
    assert '<th scope="col" class="num wm-col-weight">Weight</th>' in c
