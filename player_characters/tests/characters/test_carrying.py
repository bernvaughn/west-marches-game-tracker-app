"""Carried weight on the character sheet (S3 / U155).

Covers calculate_carried_weight, default_capacity, carrying_capacity,
format_carrying_line, over_capacity, the _carrying.html partial, and the
integration rule that buying never blocks on carried weight.
"""

from datetime import date

import pytest
from django.urls import reverse

from accounts.models import Membership
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.carrying import (
    calculate_carried_weight,
    carrying_capacity,
    default_capacity,
    format_carrying_line,
    over_capacity,
)
from player_characters.models import Character
from player_characters.sheet import InventoryRow
from shops.models import Rotation, Shop, ShopStock

pytestmark = pytest.mark.django_db


def _item(club, name, weight=None, stacked=False, value_cp=10):
    return Item.objects.create(
        club=club,
        name=name,
        weight_hundredth_lb=weight,
        is_stacked=stacked,
        unit_name="ea" if stacked else "",
        value_cp=value_cp,
    )


def _row(item, owned):
    return InventoryRow(item=item, owned=owned, held=0)


def _character(club, player, strength=10, name="Aria"):
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(club=club, owner=owner, name=name, strength=strength)


def _detail_url(club, pk):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": pk})


# --- calculate_carried_weight ---


def test_calculate_carried_weight_sums_correctly(club):
    rope = _item(club, "Rope", weight=100)  # 1.0 lb
    torch = _item(club, "Torch", weight=50)  # 0.5 lb
    rows = [_row(rope, 3), _row(torch, 4)]
    total, unweighted_count, unweighted_names = calculate_carried_weight(rows)
    assert total == 500  # 3.0 lb + 2.0 lb = 5.0 lb = 500 hundredths
    assert unweighted_count == 0
    assert unweighted_names == []


def test_stacked_items_use_units(club):
    arrow = _item(club, "Arrow", weight=15, stacked=True)  # 0.15 lb per unit
    rows = [_row(arrow, 20)]
    total, _, _ = calculate_carried_weight(rows)
    assert total == 300  # 20 units x 0.15 lb = 3.0 lb = 300 hundredths


def test_non_stacked_items_use_owned(club):
    torch = _item(club, "Torch", weight=100, stacked=False)  # 1.0 lb each
    rows = [_row(torch, 5)]
    total, _, _ = calculate_carried_weight(rows)
    assert total == 500  # 5 items x 1.0 lb = 5.0 lb = 500 hundredths


def test_unweighted_items_counted_and_named(club):
    rope = _item(club, "Rope", weight=100)
    mystery = _item(club, "Mystery", weight=None)
    rows = [_row(rope, 2), _row(mystery, 1)]
    total, count, names = calculate_carried_weight(rows)
    assert total == 200
    assert count == 1
    assert names == ["Mystery"]


# --- capacity ---


def test_default_capacity_15_x_strength(club, player):
    character = _character(club, player, strength=10)
    assert default_capacity(character) == 15000  # 150 lb


def test_default_capacity_blank_strength(club, player):
    character = _character(club, player, strength=None)
    assert default_capacity(character) is None


def test_carrying_capacity_delegates_to_default_capacity(club, player):
    character = _character(club, player, strength=10)
    assert carrying_capacity(character) == default_capacity(character)


# --- formatting ---


def test_format_carrying_line_with_capacity():
    assert format_carrying_line(6250, 15000) == "Carrying 62.5 lb of 150 lb"


def test_format_carrying_line_without_capacity():
    assert format_carrying_line(6250, None) == "Carrying 62.5 lb"


# --- over capacity ---


def test_over_capacity_true():
    assert over_capacity(16000, 15000) is True


def test_over_capacity_false():
    assert over_capacity(15000, 15000) is False
    assert over_capacity(10000, 15000) is False


def test_over_capacity_no_capacity():
    assert over_capacity(16000, None) is False


# --- sheet / template ---


@pytest.mark.story("U155")
def test_sheet_line_with_capacity(club, login, player):
    character = _character(club, player, strength=10)  # capacity 150 lb
    item = _item(club, "Rope", weight=625)  # 6.25 lb
    record(character, "award", [Line(item=item, quantity=10)])  # 62.5 lb carried
    html = login(player).get(_detail_url(club, character.pk)).content.decode()
    assert "Carrying 62.5 lb of 150 lb" in html


@pytest.mark.story("U155")
def test_sheet_line_blank_strength(club, login, player):
    character = _character(club, player, strength=None)  # no capacity
    item = _item(club, "Rope", weight=625)
    record(character, "award", [Line(item=item, quantity=10)])  # 62.5 lb carried
    html = login(player).get(_detail_url(club, character.pk)).content.decode()
    assert "Carrying 62.5 lb" in html
    assert "of 150 lb" not in html


@pytest.mark.story("U155")
def test_sheet_shows_unweighted_note(club, login, player):
    character = _character(club, player, strength=10)
    weighted = _item(club, "Rope", weight=100)
    for name in ("Mystery", "Thing", "Stuff"):
        record(character, "award", [Line(item=_item(club, name, weight=None), quantity=1)])
    record(character, "award", [Line(item=weighted, quantity=1)])
    html = login(player).get(_detail_url(club, character.pk)).content.decode()
    assert "3 items have no weight listed" in html


@pytest.mark.story("U155")
def test_sheet_shows_calm_over_capacity_note(club, login, player):
    character = _character(club, player, strength=10)  # capacity 150 lb
    item = _item(club, "Anvil", weight=20000)  # 200 lb
    record(character, "award", [Line(item=item, quantity=1)])  # 200 lb carried
    html = login(player).get(_detail_url(club, character.pk)).content.decode()
    assert "Carrying 200 lb of 150 lb" in html
    assert "Over capacity" in html
    assert "wm-sheet-note" in html  # calm styling, not a red error


# --- integration: buying never blocks on weight ---


@pytest.mark.story("U155")
def test_buy_over_capacity_succeeds(club, login, player):
    # Character is over capacity (200 lb carried vs 150 lb capacity).
    character = _character(club, player, strength=10)
    anvil = _item(club, "Anvil", weight=20000, value_cp=10)  # 200 lb
    record(character, "award", [Line(item=anvil, quantity=1)])
    record(character, "award", [Line(coins=1000)])  # funds to buy

    shop = Shop.objects.create(
        club=club, name="Lantern", keeper_name="Marta", sell_percent=100, buy_percent=50
    )
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    torch = _item(club, "Torch", weight=None, value_cp=10)
    stock = ShopStock.objects.create(shop=shop, item=torch, quantity=2)

    client = login(player)
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    resp = client.post(url, {"quantity": 1})
    assert resp.status_code == 302
    assert resp.url == reverse("shops:detail", args=[club.slug, shop.pk])
    assert LedgerEntry.objects.filter(kind="purchase").count() == 1
