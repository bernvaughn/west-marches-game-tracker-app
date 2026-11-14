import pytest
from django.urls import reverse

from accounts.models import Membership
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import Line, available_coins, coin_balance, item_quantities, record
from player_characters import junk, player_shop
from player_characters.models import Character, JunkMark, Trade, TradeLine

pytestmark = [pytest.mark.django_db, pytest.mark.story("U66")]
HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def seller(character, item):
    """Aria owns 5 Rope, marks 3 as junk, shop open."""
    record(character, "award", [Line(item=item, quantity=5)])
    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()
    return character


@pytest.fixture
def buyer(other_character):
    record(other_character, "award", [Line(coins=1000)])
    return other_character


def stall(club, seller):
    return reverse("shops:player_shop", args=[club.slug, seller.pk])


def buy_url(club, seller, item):
    return reverse("shops:player_shop_buy", args=[club.slug, seller.pk, item.pk])


# --- listing -------------------------------------------------------------


def test_listing_is_junk_quantity(seller, item):
    rows = player_shop.listed_rows(seller)
    assert [(r.item, r.quantity, r.price) for r in rows] == [(item, 3, 100)]
    assert player_shop.has_listing(seller)
    assert player_shop.listed_quantity(seller) == 3


def test_listing_capped_by_available_and_returns_after_release(seller, item, other_character, club):
    trade = Trade.objects.create(
        club=club, sender=seller, receiver=other_character, status="requested"
    )
    TradeLine.objects.create(trade=trade, from_sender=True, item=item, quantity=4)
    assert player_shop.listed_rows(seller)[0].quantity == 1
    trade.status = "cancelled"
    trade.save()
    assert player_shop.listed_rows(seller)[0].quantity == 3


def test_fully_held_item_left_out(seller, item, other_character, club):
    trade = Trade.objects.create(
        club=club, sender=seller, receiver=other_character, status="requested"
    )
    TradeLine.objects.create(trade=trade, from_sender=True, item=item, quantity=5)
    assert player_shop.listed_rows(seller) == []
    assert not player_shop.has_listing(seller)


def test_closed_shop_lists_nothing(seller):
    seller.shop_open = False
    seller.save()
    assert player_shop.listed_rows(seller) == []


def test_switch_default_off(character):
    assert character.shop_open is False


# --- stall page ----------------------------------------------------------


def test_stall_page_lists_items_with_buy(login, club, seller, buyer, item):
    resp = login(buyer.owner.user).get(stall(club, seller))
    body = resp.content.decode()
    assert resp.status_code == 200
    assert "Aria&#x27;s stall" in body or "Aria's stall" in body
    assert item.name in body
    assert buy_url(club, seller, item) in body
    assert "Your inventory" in body


def test_closed_stall_404_for_others(login, club, seller, buyer):
    seller.shop_open = False
    seller.save()
    assert login(buyer.owner.user).get(stall(club, seller)).status_code == 404


def test_empty_stall_404_for_others(login, club, seller, buyer):
    JunkMark.objects.all().delete()
    assert login(buyer.owner.user).get(stall(club, seller)).status_code == 404


def test_gm_gets_404_when_closed(login, club, seller, game_master):
    seller.shop_open = False
    seller.save()
    assert login(game_master).get(stall(club, seller)).status_code == 404


def test_owner_sees_own_shop_without_buy(login, club, seller, player, item):
    body = login(player).get(stall(club, seller)).content.decode()
    assert "This is your shop" in body
    assert buy_url(club, seller, item) not in body
    assert reverse("characters:detail", args=[club.slug, seller.pk]) in body


def test_owner_can_open_closed_empty_stall(login, club, character, player):
    resp = login(player).get(stall(club, character))
    assert resp.status_code == 200
    assert "This is your shop" in resp.content.decode()
    assert "closed" in resp.content.decode()


def test_cross_club_isolation(login, club, other_club, seller, buyer, other_player):
    from accounts.models import User

    other_user = User.objects.create_user("x@example.com", password="pw", display_name="X")
    Membership.objects.create(user=other_user, club=other_club)
    c = login(other_user)
    # Other club's slug with this club's character id: 404.
    assert c.get(reverse("shops:player_shop", args=[other_club.slug, seller.pk])).status_code == 404
    item = Item.objects.filter(club=club).first()
    url = reverse("shops:player_shop_buy", args=[other_club.slug, seller.pk, item.pk])
    assert c.get(url).status_code == 404
    assert c.post(url, {"quantity": 1}).status_code == 404
    # Not a member of this club at all: no access.
    assert c.get(stall(club, seller)).status_code in (403, 404)


# --- buying --------------------------------------------------------------


def test_buy_moves_coins_and_items_and_lowers_junk(login, club, seller, buyer, item):
    resp = login(buyer.owner.user).post(buy_url(club, seller, item), {"quantity": 2})
    assert resp.status_code == 302
    assert resp.url == stall(club, seller)
    assert coin_balance(buyer) == 800
    assert coin_balance(seller) == 200
    assert item_quantities(buyer)[item.pk] == 2
    assert item_quantities(seller)[item.pk] == 3
    assert JunkMark.objects.get(character=seller, item=item).quantity == 1
    entries = LedgerEntry.objects.filter(kind="player_shop")
    assert entries.count() == 2
    assert {e.character for e in entries} == {seller, buyer}


def test_buy_last_goes_to_street(login, club, seller, buyer, item):
    resp = login(buyer.owner.user).post(buy_url(club, seller, item), {"quantity": 3})
    assert resp.url == reverse("shops:index", args=[club.slug])
    assert not JunkMark.objects.filter(character=seller).exists()


def test_htmx_buy_returns_redirect_header(login, club, seller, buyer, item):
    resp = login(buyer.owner.user).post(buy_url(club, seller, item), {"quantity": 1}, **HX)
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == stall(club, seller)


def test_plain_buy_page_and_modal(login, club, seller, buyer, item):
    c = login(buyer.owner.user)
    page = c.get(buy_url(club, seller, item)).content.decode()
    assert "<html" in page and "Buying as <strong>Borin" in page
    assert "<dt>Remaining</dt><dd>3 listed</dd>" in page
    frag = c.get(buy_url(club, seller, item), **HX).content.decode()
    assert "<html" not in frag and "modal-header" in frag


def test_more_than_listed_refused(login, club, seller, buyer, item):
    resp = login(buyer.owner.user).post(buy_url(club, seller, item), {"quantity": 4})
    assert resp.status_code == 200
    assert LedgerEntry.objects.filter(kind="player_shop").count() == 0
    assert coin_balance(buyer) == 1000


def test_service_refusals(seller, buyer, item, other_club, second_seller_same_owner):
    with pytest.raises(player_shop.PlayerShopError):
        player_shop.buy_from(buyer, seller, item, 4)
    with pytest.raises(player_shop.PlayerShopError):
        player_shop.buy_from(buyer, seller, item, 0)
    with pytest.raises(player_shop.PlayerShopError, match="your shop"):
        player_shop.buy_from(seller, seller, item, 1)
    with pytest.raises(player_shop.PlayerShopError, match="your shop"):
        player_shop.buy_from(second_seller_same_owner, seller, item, 1)
    foreign = Character.objects.create(
        club=other_club, owner=_foreign_owner(other_club), name="Fenn"
    )
    with pytest.raises(player_shop.PlayerShopError, match="club"):
        player_shop.buy_from(foreign, seller, item, 1)
    seller.shop_open = False
    seller.save()
    with pytest.raises(player_shop.PlayerShopError, match="closed"):
        player_shop.buy_from(buyer, seller, item, 1)
    assert LedgerEntry.objects.filter(kind="player_shop").count() == 0


def _foreign_owner(other_club):
    from accounts.models import User

    user = User.objects.create_user("f@example.com", password="pw", display_name="F")
    return Membership.objects.create(user=user, club=other_club)


@pytest.fixture
def second_seller_same_owner(club, character):
    c = Character.objects.create(club=club, owner=character.owner, name="Brannoc")
    record(c, "award", [Line(coins=1000)])
    return c


def test_own_character_buy_page_refused(login, club, seller, player, item):
    c = login(player)
    body = c.get(buy_url(club, seller, item)).content.decode()
    assert "This is your shop" in body and "Buy as" not in body
    c.post(buy_url(club, seller, item), {"quantity": 1})
    assert LedgerEntry.objects.filter(kind="player_shop").count() == 0


def test_cannot_afford_shown(login, club, seller, other_character, item):
    record(other_character, "award", [Line(coins=50)])
    resp = login(other_character.owner.user).post(buy_url(club, seller, item), {"quantity": 1})
    assert resp.status_code == 200
    assert "cannot afford" in resp.content.decode()
    assert available_coins(other_character) == 50
    assert JunkMark.objects.get(character=seller).quantity == 3


def test_closed_shop_buy_404(login, club, seller, buyer, item):
    seller.shop_open = False
    seller.save()
    assert (
        login(buyer.owner.user).post(buy_url(club, seller, item), {"quantity": 1}).status_code
        == 404
    )


def test_buy_is_atomic(seller, buyer, item, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(junk, "reduce_junk", boom)
    with pytest.raises(RuntimeError):
        player_shop.buy_from(buyer, seller, item, 1)
    assert LedgerEntry.objects.filter(kind="player_shop").count() == 0
    assert coin_balance(buyer) == 1000


# --- ledger --------------------------------------------------------------


def test_ledgers_show_player_shop_kind(login, club, seller, buyer, item, game_master):
    player_shop.buy_from(buyer, seller, item, 1)
    c = login(game_master)
    for url in (
        reverse("ledger:character_history", args=[club.slug, seller.pk]),
        reverse("ledger:character_history", args=[club.slug, buyer.pk]),
        reverse("ledger:index", args=[club.slug]),
    ):
        assert "Player shop" in c.get(url).content.decode()
    resp = c.get(reverse("ledger:index", args=[club.slug]), {"kind": "player_shop"})
    assert "Player shop" in resp.content.decode()
    resp = c.get(reverse("ledger:index", args=[club.slug]), {"kind": "purchase"})
    assert "Sold 1" not in resp.content.decode()


# --- sheet switch --------------------------------------------------------


def toggle(club, character):
    return reverse("characters:shop_toggle", args=[club.slug, character.pk])


def test_sheet_shows_switch_off_by_default(login, club, character, player):
    body = (
        login(player)
        .get(reverse("characters:detail", args=[club.slug, character.pk]))
        .content.decode()
    )
    assert "Sell my junk in my shop" in body
    assert "Listed in your shop" not in body


@pytest.mark.parametrize("who", ["player", "game_master", "club_admin"])
def test_privileged_can_flip(request, login, club, character, who):
    user = request.getfixturevalue(who)
    resp = login(user).post(toggle(club, character), {"shop_open": "on"})
    assert resp.status_code == 302
    character.refresh_from_db()
    assert character.shop_open
    login(user).post(toggle(club, character), {})
    character.refresh_from_db()
    assert not character.shop_open


def test_other_player_cannot_flip_or_see(login, club, character, other_player):
    c = login(other_player)
    assert c.post(toggle(club, character), {"shop_open": "on"}).status_code == 403
    character.refresh_from_db()
    assert not character.shop_open
    url = reverse("characters:detail", args=[club.slug, character.pk])
    body = c.get(url).content.decode()
    assert "Sell my junk in my shop" not in body


def test_toggle_get_405(login, club, character, player):
    assert login(player).get(toggle(club, character)).status_code == 405


def test_toggle_htmx(login, club, character, player):
    resp = login(player).post(toggle(club, character), {"shop_open": "on"}, **HX)
    assert resp.status_code == 204 and "HX-Redirect" in resp


def test_sheet_shows_listed_line_when_on(login, club, seller, player):
    body = (
        login(player)
        .get(reverse("characters:detail", args=[club.slug, seller.pk]))
        .content.decode()
    )
    assert "Listed in your shop" in body
    assert "3 items" in body
    assert stall(club, seller) in body


def test_toggle_cross_club(login, club, other_club, character):
    from accounts.models import User

    user = User.objects.create_user("y@example.com", password="pw", display_name="Y")
    Membership.objects.create(user=user, club=other_club)
    url = reverse("characters:shop_toggle", args=[other_club.slug, character.pk])
    assert login(user).post(url, {"shop_open": "on"}).status_code == 404


def test_stall_heading_above_banner_and_own_alert_before_banner(login, club, seller):
    page = login(seller.owner.user).get(stall(club, seller)).content.decode()
    banner = page.index("wm-player-shop-banner")
    assert page.index("wm-page-header") < page.index("<h1") < banner
    assert page.count("<h1") == 1
    assert page.index("This is your shop.") < banner
