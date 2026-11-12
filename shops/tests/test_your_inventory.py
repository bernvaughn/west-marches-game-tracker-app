from datetime import date

import pytest
from django.urls import reverse

from items.models import Item
from ledger.services import Line, record
from shops.models import Rotation, ShopStock
from shops.services import buy_price

pytestmark = pytest.mark.django_db


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return shop


def card(client, club, shop):
    b = client.get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()
    return b[b.index('id="your-inventory"') :]


@pytest.mark.story("U46")
def test_card_shows_character_coins_items_and_prices(
    login, player, club, open_shop, character, item
):
    record(character, "award", [Line(coins=500), Line(item=item, quantity=3)])
    gem = Item.objects.create(club=club, name="Gem", value_cp=333)
    record(character, "award", [Line(item=gem, quantity=1)])
    ShopStock.objects.create(shop=open_shop, item=gem, quantity=1, buy_percent=80)
    c = card(login(player), club, open_shop)
    assert "Aria" in c and "Held" in c and "Available" in c
    assert "Rope" in c and "Gem" in c
    assert buy_price(open_shop, gem) == 333 * 80 // 100
    assert buy_price(open_shop, item) == 50


@pytest.mark.story("U46")
def test_prices_match_buy_price(login, player, club, open_shop, character, item):
    from shops.views.browse import _inventory_context

    gem = Item.objects.create(club=club, name="Gem", value_cp=333)
    record(character, "award", [Line(item=gem, quantity=1), Line(item=item, quantity=1)])
    ShopStock.objects.create(shop=open_shop, item=gem, quantity=1, buy_percent=80)

    class Req:
        pass

    from unittest import mock

    with mock.patch("shops.views.browse.selected_character", return_value=character):
        rows = _inventory_context(Req(), open_shop)["inventory_rows"]
    assert {r["item"].pk: r["price"] for r in rows} == {
        gem.pk: buy_price(open_shop, gem),
        item.pk: buy_price(open_shop, item),
    }


@pytest.mark.story("U46")
def test_no_character_state(login, player, club, open_shop):
    c = card(login(player), club, open_shop)
    assert "You have no character in this club." in c
    assert reverse("characters:create", args=[club.slug]) in c


@pytest.mark.story("U46")
def test_other_players_character_never_shown(
    login, player, other_player, club, open_shop, other_character
):
    c = card(login(player), club, open_shop)
    assert "Borin" not in c


@pytest.mark.story("U46")
def test_gm_sees_only_own_character(login, game_master, club, open_shop, character):
    c = card(login(game_master), club, open_shop)
    assert "Aria" not in c and "You have no character" in c


@pytest.mark.story("U46")
def test_cross_club(login, player, club, other_club, other_shop, open_shop, character):
    assert (
        login(player)
        .get(reverse("shops:detail", args=[other_club.slug, other_shop.id]))
        .status_code
        == 404
    )
    # same card never lists another club's data
    assert "Elsewhere" not in card(login(player), club, open_shop)


@pytest.mark.story("U46")
def test_query_count_flat(login, player, club, open_shop, character, django_assert_max_num_queries):
    client = login(player)
    for n in range(6):
        it = Item.objects.create(club=club, name=f"Thing{n}", value_cp=10 + n)
        record(character, "award", [Line(item=it, quantity=1)])
    with django_assert_max_num_queries(40):
        card(client, club, open_shop)
