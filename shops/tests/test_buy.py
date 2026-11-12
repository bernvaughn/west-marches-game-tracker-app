import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import InsufficientFunds, Line, record
from player_characters.models import Trade, TradeLine
from shops.buying import buy
from shops.models import ShopStock
from shops.services import AlreadySold, NotStocked, ShopClosed

pytestmark = pytest.mark.django_db


@pytest.fixture
def funded_other(other_character):
    record(other_character, "award", [Line(coins=1000)])
    return other_character


def url(club, shop, stock):
    return reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])


def purchases():
    return LedgerEntry.objects.filter(kind="purchase")


@pytest.mark.story("C2")
def test_buy_writes_purchase_entry(shop, always_open, stock, rich_character, player):
    entry = buy(rich_character, stock, actor=player)
    assert entry.kind == "purchase"
    assert entry.shop == shop
    lines = {(line.coins, line.item_id, line.quantity) for line in entry.lines.all()}
    assert (-100, None, 0) in lines or any(line.coins == -100 for line in entry.lines.all())
    assert any(line.item_id == stock.item_id and line.quantity == 1 for line in entry.lines.all())
    assert purchases().count() == 1
    stock.refresh_from_db()
    assert stock.quantity == 1
    assert "Bought 1" in entry.note


@pytest.mark.story("C2")
def test_buy_view_redirects_and_records(
    club, shop, always_open, stock, rich_character, player, login
):
    client = login(player)
    resp = client.post(url(club, shop, stock), {"character": rich_character.pk, "quantity": 1})
    assert resp.status_code == 302
    assert resp.url == reverse("shops:detail", args=[club.slug, shop.pk])
    entry = purchases().get()
    assert entry.created_by == player


@pytest.mark.story("C2")
def test_buy_get_shows_form(club, shop, always_open, stock, rich_character, player, login):
    resp = login(player).get(url(club, shop, stock))
    assert resp.status_code == 200
    assert b"Aria" in resp.content


@pytest.mark.story("C2")
def test_cannot_afford(club, shop, always_open, stock, character, player, login):
    with pytest.raises(InsufficientFunds):
        buy(character, stock)
    resp = login(player).post(url(club, shop, stock), {"character": character.pk, "quantity": 1})
    assert resp.status_code == 200
    assert "cannot afford this: needs 1 gp, has 0 cp available" in resp.content.decode()
    assert purchases().count() == 0
    stock.refresh_from_db()
    assert stock.quantity == 2


@pytest.mark.story("C2")
def test_held_coins_cannot_be_spent(club, shop, always_open, stock, rich_character, funded_other):
    trade = Trade.objects.create(club=club, sender=rich_character, receiver=funded_other)
    TradeLine.objects.create(trade=trade, from_sender=True, coins=950)
    with pytest.raises(InsufficientFunds):
        buy(rich_character, stock)
    assert purchases().count() == 0
    stock.refresh_from_db()
    assert stock.quantity == 2


@pytest.mark.story("C3")
def test_last_unit_goes_to_one_buyer(
    club, shop, always_open, stock, rich_character, funded_other, other_player, login
):
    stock.quantity = 1
    stock.save()
    buy(rich_character, stock)
    with pytest.raises(AlreadySold):
        buy(funded_other, stock)
    assert purchases().count() == 1
    resp = login(other_player).post(
        url(club, shop, stock), {"character": funded_other.pk, "quantity": 1}
    )
    assert resp.status_code == 200
    assert "Already sold" in resp.content.decode()
    assert purchases().count() == 1


@pytest.mark.story("C3")
def test_stale_stock_object_fails(shop, always_open, stock, rich_character, funded_other):
    stock.quantity = 1
    stock.save()
    stale = ShopStock.objects.get(pk=stock.pk)
    buy(rich_character, ShopStock.objects.get(pk=stock.pk))
    with pytest.raises(AlreadySold):
        buy(funded_other, stale)
    assert purchases().count() == 1
    stock.refresh_from_db()
    assert stock.quantity == 0


@pytest.mark.story("U9")
def test_unlimited_stock_stays_null(shop, always_open, unlimited_stock, rich_character):
    entry = buy(rich_character, unlimited_stock, quantity=3)
    unlimited_stock.refresh_from_db()
    assert unlimited_stock.quantity is None
    assert entry.shop == shop
    assert any(line.coins == -30 for line in entry.lines.all())


@pytest.mark.story("C2")
def test_other_owners_character_ignored(
    club, shop, always_open, stock, funded_other, player, login
):
    login(player).post(url(club, shop, stock), {"character": funded_other.pk, "quantity": 1})
    assert not purchases().filter(character=funded_other).exists()


@pytest.mark.story("C2")
def test_closed_shop_404(club, closed_shop, item, rich_character, player, login):
    closed_stock = ShopStock.objects.create(shop=closed_shop, item=item, quantity=2)
    client = login(player)
    assert client.get(url(club, closed_shop, closed_stock)).status_code == 404
    resp = client.post(
        url(club, closed_shop, closed_stock), {"character": rich_character.pk, "quantity": 1}
    )
    assert resp.status_code == 404
    with pytest.raises(ShopClosed):
        buy(rich_character, closed_stock)
    assert purchases().count() == 0


@pytest.mark.story("C2")
def test_retired_item_404(club, shop, always_open, stock, rich_character, player, login):
    stock.item.retired = True
    stock.item.save()
    assert login(player).get(url(club, shop, stock)).status_code == 404
    with pytest.raises(NotStocked):
        buy(rich_character, stock)


@pytest.mark.story("C2")
def test_quantity_above_stock_rejected(
    club, shop, always_open, stock, rich_character, player, login
):
    resp = login(player).post(
        url(club, shop, stock), {"character": rich_character.pk, "quantity": 5}
    )
    assert resp.status_code == 200
    assert resp.context["form"].errors.get("quantity")
    assert purchases().count() == 0


@pytest.mark.story("C2")
def test_cross_club_ids_404(club, shop, other_shop, always_open, stock, player, login, other_club):
    foreign_item = Item.objects.create(club=other_club, name="Gem", value_cp=5)
    foreign = ShopStock.objects.create(shop=other_shop, item=foreign_item, quantity=1)
    client = login(player)
    assert client.get(url(club, other_shop, foreign)).status_code == 404
    assert client.get(url(club, shop, foreign)).status_code == 404
    assert (
        client.get(reverse("shops:buy", args=[club.slug, other_shop.pk, stock.pk])).status_code
        == 404
    )


@pytest.mark.story("C2")
def test_non_member_404(club, shop, always_open, stock, login, db):
    from accounts.models import User

    outsider = User.objects.create_user("out@example.com", password="pw", display_name="Out")
    assert login(outsider).get(url(club, shop, stock)).status_code == 404
