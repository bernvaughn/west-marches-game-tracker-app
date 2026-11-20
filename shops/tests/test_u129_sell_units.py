"""Sell and set aside units (U129): shop sales, confirm modals, player stalls."""

import pytest
from django.urls import reverse

from items.models import Item
from items.stacked import bundle_price, sale_price, unit_label
from ledger.models import LedgerEntry
from ledger.services import Line, available_coins, item_quantities, record
from player_characters.junk import junk_value, junk_value_at, set_junk
from player_characters.models import Character, JunkMark
from player_characters.player_shop import PlayerShopError, buy_from, listed_rows, stall_price
from shops.models import Rotation, ShopStock
from shops.selling import SellLineError, buy_percent_for, sale_total, sell, sell_many
from shops.services import ShopError

pytestmark = [pytest.mark.story("U129"), pytest.mark.django_db]


def _make_stacked(club, name, unit_name, value_cp, value_units):
    return Item.objects.create(
        club=club,
        name=name,
        is_stacked=True,
        unit_name=unit_name,
        value_cp=value_cp,
        value_units=value_units,
    )


@pytest.fixture
def parchment(club):
    """Parchment: 100 cp per 10 sheets."""
    return _make_stacked(club, "Parchment", "sheet", 100, 10)


@pytest.fixture
def rope(club):
    """Rope: 100 cp per 50 ft."""
    return _make_stacked(club, "Rope", "ft", 100, 50)


@pytest.fixture
def tiny(club):
    """A near-worthless stacked item: 1 cp per 100 units."""
    return _make_stacked(club, "Sawdust", "g", 1, 100)


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date="2000-01-01").shops.add(shop)
    return shop


def award(character, lines):
    record(character, "award", lines)


# --- property: split sales never beat one sale (DB-backed) ----------------


@pytest.mark.parametrize("value_cp", [1, 3, 7, 13, 25, 50, 100, 300])
@pytest.mark.parametrize("value_units", [2, 3, 7, 10, 20, 50])
@pytest.mark.parametrize("buy_percent", [0, 1, 25, 50, 75, 100, 150])
def test_split_sales_never_beat_one_sale(club, value_cp, value_units, buy_percent):
    thing = _make_stacked(club, "Thing", "unit", value_cp, value_units)
    total = sale_price(thing, 100, buy_percent)
    assert sum(sale_price(thing, p, buy_percent) for p in [50, 50]) <= total
    assert sum(sale_price(thing, p, buy_percent) for p in [30, 30, 40]) <= total
    assert sum(sale_price(thing, p, buy_percent) for p in [1, 1, 98]) <= total


# --- property: buy then sell back never profits when sell pct >= buy pct --


@pytest.mark.parametrize("value_cp", [0, 1, 3, 7, 13, 25, 50, 100, 300])
@pytest.mark.parametrize("value_units", [1, 2, 3, 7, 10, 20, 50])
@pytest.mark.parametrize("sell_percent", [0, 1, 25, 50, 75, 100, 150])
@pytest.mark.parametrize("buy_percent", [0, 1, 25, 50, 75, 100])
def test_buy_then_sell_back_never_profits_when_sell_ge_buy(
    club, value_cp, value_units, sell_percent, buy_percent
):
    if sell_percent < buy_percent:
        pytest.skip("only the sell >= buy case is the profit-free guarantee")
    thing = _make_stacked(club, "Thing", "unit", value_cp, value_units)
    for bundle in (1, 5, 13, 50, 100):
        cost = bundle_price(thing, bundle, sell_percent)
        revenue = sale_price(thing, bundle, buy_percent)
        assert revenue <= cost, (
            f"profit: buy {bundle} for {cost} cp, sell back for {revenue} cp "
            f"(sell {sell_percent}% >= buy {buy_percent}%)"
        )


# --- shop sale: price floored once from the total units ------------------


def test_stacked_sale_pays_floor_once_from_total(club, player, character, open_shop, parchment):
    """7 sheets at 50%: floor(100 * 7 * 50 / (100 * 10)) = 35 cp."""
    award(character, [Line(item=parchment, quantity=7), Line(coins=100)])
    set_junk(character, parchment, 7, player)
    sell_many(character, open_shop, [(parchment, 7)], actor=player)
    assert available_coins(character) == 135
    assert item_quantities(character).get(parchment.pk, 0) == 0


def test_stacked_sale_pays_floor_once_not_per_unit(club, player, character, open_shop, parchment):
    """At 25%: floor(100 * 7 * 25 / 1000) = 17 cp once, not 7 * 2 = 14 cp per unit."""
    ShopStock.objects.create(shop=open_shop, item=parchment, buy_percent=25)
    award(character, [Line(item=parchment, quantity=7), Line(coins=100)])
    set_junk(character, parchment, 7, player)
    sell_many(character, open_shop, [(parchment, 7)], actor=player)
    assert available_coins(character) == 117


def test_single_stacked_unit_worth_less_than_one_cp_refused(
    club, player, character, open_shop, parchment
):
    """1 sheet at 5%: floor(100 * 1 * 5 / 1000) = 0 cp -> refused, nothing written."""
    ShopStock.objects.create(shop=open_shop, item=parchment, buy_percent=5)
    award(character, [Line(item=parchment, quantity=1), Line(coins=50)])
    set_junk(character, parchment, 1, player)
    before = LedgerEntry.objects.count()
    with pytest.raises(ShopError, match="worth less than 1 cp"):
        sell(character, open_shop, parchment, 1, actor=player)
    assert LedgerEntry.objects.count() == before
    assert item_quantities(character).get(parchment.pk, 0) == 1
    assert available_coins(character) == 50


def test_sell_many_all_or_nothing_when_one_line_is_zero(
    club, player, character, open_shop, parchment, rope
):
    ShopStock.objects.create(shop=open_shop, item=parchment, buy_percent=5)
    award(character, [Line(item=parchment, quantity=1), Line(item=rope, quantity=50)])
    set_junk(character, parchment, 1, player)
    set_junk(character, rope, 50, player)
    before = LedgerEntry.objects.count()
    with pytest.raises(SellLineError):
        sell_many(character, open_shop, [(parchment, 1), (rope, 50)], actor=player)
    assert LedgerEntry.objects.count() == before
    assert item_quantities(character).get(parchment.pk, 0) == 1
    assert item_quantities(character).get(rope.pk, 0) == 50


def test_stacked_sale_lowers_junk_mark(club, player, character, open_shop, parchment):
    award(character, [Line(item=parchment, quantity=10)])
    set_junk(character, parchment, 10, player)
    sell_many(character, open_shop, [(parchment, 4)], actor=player)
    mark = JunkMark.objects.filter(character=character, item=parchment).first()
    assert mark is not None and mark.quantity == 6


def test_junk_value_and_junk_value_at_use_stacked_pricing(
    club, player, character, open_shop, parchment
):
    award(character, [Line(item=parchment, quantity=10)])
    set_junk(character, parchment, 10, player)
    # junk_value at 100%: floor(100 * 10 * 100 / 1000) = 100 cp
    assert junk_value(character) == 100
    # shop sale at 50%: floor(100 * 10 * 50 / 1000) = 50 cp
    assert junk_value_at(character, open_shop) == 50


# --- confirm modal: units and exact coins ---------------------------------


def test_confirm_modal_shows_units_and_exact_coins(
    club, login, player, character, open_shop, parchment
):
    award(character, [Line(item=parchment, quantity=10)])
    set_junk(character, parchment, 2, player)
    c = login(player)
    url = reverse("shops:sell_item", args=[club.slug, open_shop.pk, parchment.pk])
    r = c.post(url, {"character": character.id, "quantity": 5}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert unit_label(parchment, 5) in body  # "5 sheet Parchment"
    # 5 sheets at 50%: floor(100 * 5 * 50 / 1000) = 25 cp = 2 sp 5 cp
    assert "2 sp" in body and "5 cp" in body


def test_confirm_page_shows_units_and_exact_coins_without_htmx(
    club, login, player, character, open_shop, parchment
):
    award(character, [Line(item=parchment, quantity=10)])
    set_junk(character, parchment, 2, player)
    c = login(player)
    url = reverse("shops:sell_item", args=[club.slug, open_shop.pk, parchment.pk])
    # No "confirmed": shows the confirm page as a full page (200).
    r = c.post(url, {"character": character.id, "quantity": 5})
    assert r.status_code == 200
    body = r.content.decode()
    assert unit_label(parchment, 5) in body  # "5 sheet Parchment"
    # 5 sheets at 50%: floor(100 * 5 * 50 / 1000) = 25 cp = 2 sp 5 cp
    assert "2 sp" in body and "5 cp" in body
    # Confirming sells and redirects to the shop detail.
    before = available_coins(character)
    r = c.post(url, {"character": character.id, "quantity": 5, "confirmed": "1"})
    assert r.status_code == 302
    assert available_coins(character) == before + 25
    assert item_quantities(character).get(parchment.pk, 0) == 5  # 10 - 5 sold


def test_confirm_refuses_zero_cp_stacked_sale_before_confirm(
    club, login, player, character, open_shop, parchment
):
    ShopStock.objects.create(shop=open_shop, item=parchment, buy_percent=5)
    award(character, [Line(item=parchment, quantity=1)])
    # no junk mark: quantity 1 > junk 0, and 1 sheet pays 0 cp -> refused before confirm
    c = login(player)
    url = reverse("shops:sell_item", args=[club.slug, open_shop.pk, parchment.pk])
    r = c.post(url, {"character": character.id, "quantity": 1}, HTTP_HX_REQUEST="true")
    assert r.status_code == 204  # redirects with error
    page = c.get(r.headers["HX-Redirect"]).content.decode()
    assert "worth less than 1 cp" in page
    assert item_quantities(character).get(parchment.pk, 0) == 1


def test_normal_item_zero_value_still_sells(club, login, player, character, open_shop):
    worthless = Item.objects.create(club=club, name="Junk", value_cp=0)
    award(character, [Line(item=worthless, quantity=2)])
    set_junk(character, worthless, 2, player)
    c = login(player)
    url = reverse("shops:sell_item", args=[club.slug, open_shop.pk, worthless.pk])
    r = c.post(url, {"character": character.id, "quantity": 2}, HTTP_HX_REQUEST="true")
    assert r.status_code == 204  # sold straight through (quantity within junk)
    assert item_quantities(character).get(worthless.pk, 0) == 0


# --- player stall: price floor once for the listed quantity ---------------


def test_stall_price_is_floor_once_for_listed_quantity(club, character, parchment, player):
    award(character, [Line(item=parchment, quantity=10)])
    JunkMark.objects.create(character=character, item=parchment, quantity=10)
    character.shop_open = True
    character.save()
    rows = listed_rows(character)
    assert [(r.item, r.quantity, r.price) for r in rows] == [(parchment, 10, 100)]
    assert stall_price(parchment, 10) == 100  # floor(100 * 10 * 100 / 1000)


def test_stall_sale_moves_units_between_stacks(
    club, login, player, other_player, character, other_character, parchment
):
    award(character, [Line(item=parchment, quantity=10)])
    award(other_character, [Line(coins=200)])
    JunkMark.objects.create(character=character, item=parchment, quantity=10)
    character.shop_open = True
    character.save()
    c = login(other_player)
    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, parchment.pk])
    r = c.post(url, {"quantity": 4})
    assert r.status_code == 302
    # 4 sheets cost floor(100 * 4 * 100 / 1000) = 40 cp
    assert item_quantities(other_character)[parchment.pk] == 4
    assert item_quantities(character)[parchment.pk] == 6
    entries = LedgerEntry.objects.filter(kind="player_shop")
    assert entries.count() == 2
    assert {e.character for e in entries} == {character, other_character}


def test_stall_sale_joins_existing_stack(
    club, login, player, other_player, character, other_character, parchment
):
    award(character, [Line(item=parchment, quantity=10)])
    award(other_character, [Line(item=parchment, quantity=2), Line(coins=200)])
    JunkMark.objects.create(character=character, item=parchment, quantity=10)
    character.shop_open = True
    character.save()
    c = login(other_player)
    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, parchment.pk])
    c.post(url, {"quantity": 4})
    assert item_quantities(other_character)[parchment.pk] == 6  # one pool of 6 sheets


def test_stall_refuses_zero_cp_stacked_buy(club, character, other_character, tiny, player):
    award(character, [Line(item=tiny, quantity=5)])
    award(other_character, [Line(coins=10)])
    JunkMark.objects.create(character=character, item=tiny, quantity=5)
    character.shop_open = True
    character.save()
    with pytest.raises(PlayerShopError, match="costs 0 cp"):
        buy_from(other_character, character, tiny, 1, actor=player)
    assert item_quantities(other_character).get(tiny.pk, 0) == 0
    assert item_quantities(character).get(tiny.pk, 0) == 5


def test_stall_own_shop_refused(club, login, player, character, parchment):
    award(character, [Line(item=parchment, quantity=5)])
    JunkMark.objects.create(character=character, item=parchment, quantity=5)
    character.shop_open = True
    character.save()
    c = login(player)
    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, parchment.pk])
    r = c.post(url, {"quantity": 1})
    assert r.status_code == 200
    assert "This is your shop" in r.content.decode()


def test_stall_other_club_404(club, login, player, other_club, character, parchment):
    from accounts.models import Membership, User

    foreign_user = User.objects.create_user("f@example.com", password="pw", display_name="F")
    foreign_member = Membership.objects.create(user=foreign_user, club=other_club)
    Character.objects.create(club=other_club, owner=foreign_member, name="Fenn")
    award(character, [Line(item=parchment, quantity=5)])
    JunkMark.objects.create(character=character, item=parchment, quantity=5)
    character.shop_open = True
    character.save()
    c = login(foreign_user)
    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, parchment.pk])
    assert c.get(url).status_code == 404


def test_stall_closed_404(club, login, player, other_player, character, other_character, parchment):
    award(character, [Line(item=parchment, quantity=5)])
    JunkMark.objects.create(character=character, item=parchment, quantity=5)
    character.shop_open = False
    character.save()
    award(other_character, [Line(coins=200)])
    c = login(other_player)
    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, parchment.pk])
    assert c.post(url, {"quantity": 1}).status_code == 404


def test_stall_insufficient_funds(
    club, login, player, other_player, character, other_character, parchment
):
    award(character, [Line(item=parchment, quantity=5)])
    JunkMark.objects.create(character=character, item=parchment, quantity=5)
    character.shop_open = True
    character.save()
    award(other_character, [Line(coins=5)])  # 4 sheets cost 40 cp
    c = login(other_player)
    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, parchment.pk])
    r = c.post(url, {"quantity": 4})
    assert r.status_code == 200
    assert "cannot afford" in r.content.decode()
    assert item_quantities(other_character).get(parchment.pk, 0) == 0


def test_buy_percent_for_uses_first_stock_line(club, shop, parchment):
    ShopStock.objects.create(shop=shop, item=parchment, bundle_units=10, buy_percent=20)
    ShopStock.objects.create(shop=shop, item=parchment, bundle_units=1, buy_percent=80)
    assert buy_percent_for(shop, parchment) == 80  # lowest bundle_units (1) comes first


def test_buy_percent_for_falls_back_to_shop_default(club, shop, parchment):
    ShopStock.objects.create(shop=shop, item=parchment, bundle_units=10)
    assert buy_percent_for(shop, parchment) == shop.buy_percent  # 50


def test_sale_total_uses_buy_percent_override(club, shop, parchment):
    ShopStock.objects.create(shop=shop, item=parchment, bundle_units=10, buy_percent=100)
    assert sale_total(shop, parchment, 7) == 70  # 100% of 7 sheets = 70 cp
    assert sale_total(shop, parchment, 1) == 10  # 1 sheet at 100% = 10 cp
