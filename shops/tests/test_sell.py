import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import InsufficientItems, Line, record
from player_characters.models import Trade, TradeLine
from shops.models import ShopStock
from shops.selling import sell
from shops.services import ShopClosed, ShopError

pytestmark = [pytest.mark.django_db, pytest.mark.story("U3")]


@pytest.fixture
def loot(character, item):
    record(character, "award", [Line(item=item, quantity=3)])
    return item


@pytest.fixture
def other_item(other_club):
    return Item.objects.create(club=other_club, name="Gem", value_cp=500)


def _coins(entry):
    return sum(line.coins for line in entry.lines.all())


def test_stocked_item_uses_override(character, shop, always_open, stock, loot):
    stock.buy_percent = 80
    stock.save()
    entry = sell(character, shop, loot, 2)
    assert entry.kind == "sale" and entry.shop == shop
    assert _coins(entry) == 160
    assert entry.lines.filter(item=loot, quantity=-2).count() == 1
    assert entry.lines.filter(item__isnull=True, coins=160).count() == 1
    assert entry.note == "Sold 2 × Rope to Lantern"


def test_unstocked_item_uses_default_and_no_stock_row(character, shop, always_open, loot):
    entry = sell(character, shop, loot, 1)
    assert _coins(entry) == 50
    assert not ShopStock.objects.filter(shop=shop).exists()


def test_stock_unchanged(character, shop, always_open, stock, loot):
    sell(character, shop, loot, 1)
    stock.refresh_from_db()
    assert stock.quantity == 2


def _hold(character, other_character, item, club):
    trade = Trade.objects.create(club=club, sender=character, receiver=other_character)
    TradeLine.objects.create(trade=trade, from_sender=True, item=item, quantity=3)


def test_held_item_cannot_be_sold(club, character, other_character, shop, always_open, loot):
    _hold(character, other_character, loot, club)
    before = LedgerEntry.objects.count()
    with pytest.raises(InsufficientItems):
        sell(character, shop, loot, 1)
    assert LedgerEntry.objects.count() == before


def test_closed_shop_refused(character, closed_shop, loot):
    before = LedgerEntry.objects.count()
    with pytest.raises(ShopClosed):
        sell(character, closed_shop, loot, 1)
    assert LedgerEntry.objects.count() == before


def test_quantity_zero(character, shop, always_open, loot):
    with pytest.raises(ShopError):
        sell(character, shop, loot, 0)


def test_other_club_shop_refused(character, other_shop, loot):
    with pytest.raises(ShopError):
        sell(character, other_shop, loot, 1)


def url(club, shop):
    return reverse("shops:sell", args=[club.slug, shop.id])


def test_get_lists_items(club, player, login, character, shop, always_open, loot):
    r = login(player).get(url(club, shop), {"character": character.id})
    assert r.status_code == 200
    assert b"Rope" in r.content and b"5 sp" in r.content


def test_get_shows_reduced_for_held(
    club, player, login, character, other_character, shop, always_open, loot
):
    trade = Trade.objects.create(club=club, sender=character, receiver=other_character)
    TradeLine.objects.create(trade=trade, from_sender=True, item=loot, quantity=1)
    r = login(player).get(url(club, shop), {"character": character.id})
    assert r.context["rows"][0]["quantity"] == 2


def test_post_success(club, player, login, character, shop, always_open, loot):
    r = login(player).post(
        url(club, shop),
        {"character": character.id, "item": loot.id, "quantity": 2, "confirmed": "1"},
    )
    assert r.status_code == 302
    assert r.url == reverse("shops:detail", args=[club.slug, shop.id])
    entry = LedgerEntry.objects.get(kind="sale")
    assert entry.created_by == player


def test_post_held_item_message(
    club, player, login, character, other_character, shop, always_open, loot
):
    _hold(character, other_character, loot, club)
    r = login(player).post(
        url(club, shop), {"character": character.id, "item": loot.id, "quantity": 1}
    )
    assert r.status_code == 200
    assert b"Not enough Rope available to sell." in r.content
    assert not LedgerEntry.objects.filter(kind="sale").exists()


def test_closed_shop_404(club, player, login, character, closed_shop, loot):
    c = login(player)
    assert c.get(url(club, closed_shop)).status_code == 404
    r = c.post(url(club, closed_shop), {"character": character.id, "item": loot.id})
    assert r.status_code == 404


def test_cross_club_shop_404(club, player, login, other_shop):
    assert login(player).get(url(club, other_shop)).status_code == 404


def test_other_owner_character_ignored(club, player, login, other_character, shop, always_open):
    r = login(player).get(url(club, shop), {"character": other_character.id})
    assert r.status_code == 200
    assert r.context["character"] != other_character


def test_other_club_item_404(club, player, login, character, shop, always_open, other_item):
    r = login(player).post(
        url(club, shop), {"character": character.id, "item": other_item.id, "quantity": 1}
    )
    assert r.status_code == 404
    assert not LedgerEntry.objects.filter(kind="sale").exists()


def test_non_member_404(club, other_club, login, shop, always_open, site_admin):
    from accounts.models import User

    stranger = User.objects.create_user("x@example.com", password="pw", display_name="X")
    assert login(stranger).get(url(club, shop)).status_code == 404
