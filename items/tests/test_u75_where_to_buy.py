from datetime import date

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership
from items.availability import _stall_quantities, available_item_ids, where_to_buy
from items.models import Item
from ledger.services import Line, record
from ledger.templatetags.coins import coins
from player_characters.models import Character, JunkMark, Trade, TradeLine
from player_characters.player_shop import listed_rows
from shops.models import Rotation, Shop, ShopStock

pytestmark = [pytest.mark.story("U75"), pytest.mark.django_db]

TODAY = date(2026, 11, 12)


def wtb(club, item):
    return reverse("items:where_to_buy", args=[club.slug, item.pk])


def index(club):
    return reverse("items:index", args=[club.slug])


def make_shop(club, name="Lantern", open_=True, **kw):
    shop = Shop.objects.create(club=club, name=name, sell_percent=kw.pop("sell_percent", 100), **kw)
    if open_:
        Rotation.objects.create(club=club, name=f"R-{name}", open_date=date(2000, 1, 1)).shops.add(
            shop
        )
    return shop


def make_stall(club, owner_user, name, item, mark=1, have=1, open_=True):
    m = Membership.objects.get(user=owner_user, club=club)
    ch = Character.objects.create(club=club, owner=m, name=name, shop_open=open_)
    if have:
        record(ch, "award", [Line(item=item, quantity=have)])
    JunkMark.objects.create(character=ch, item=item, quantity=mark)
    return ch


def icon_count(resp):
    return resp.content.decode().count("Where to buy")


def test_icon_only_when_for_sale(login, club, player, item):
    c = login(player)
    assert b"data-app-modal" not in c.get(index(club)).content
    shop = make_shop(club)
    stock = ShopStock.objects.create(shop=shop, item=item, quantity=2)
    r = c.get(index(club))
    assert b"bi-shop" in r.content or b"#shop" in r.content
    assert wtb(club, item).encode() in r.content
    stock.quantity = 0
    stock.save()
    assert wtb(club, item).encode() not in c.get(index(club)).content


def test_closed_shop_and_retired_excluded(login, club, player, item):
    shop = make_shop(club, open_=False)
    ShopStock.objects.create(shop=shop, item=item, quantity=None)
    assert wtb(club, item).encode() not in login(player).get(index(club)).content
    shop2 = make_shop(club, name="Open")
    ShopStock.objects.create(shop=shop2, item=item, quantity=None)
    item.retired = True
    item.save()
    assert not where_to_buy(club, item, timezone.localdate(), player)
    assert login(player).get(wtb(club, item)).status_code == 404


def test_modal_lists_shop_and_stall(login, club, player, other_player, item):
    shop = make_shop(club, sell_percent=150, symbol="★")
    ShopStock.objects.create(shop=shop, item=item, quantity=None)
    make_stall(club, other_player, "Borin", item, mark=2, have=3)
    r = login(player).get(wtb(club, item), HTTP_HX_REQUEST="true")
    html = r.content.decode()
    assert "Where to buy Rope" in html and "<html" not in html
    assert "Lantern" in html and "★" in html and "Unlimited" in html
    assert str(coins(150)) in html
    assert "Borin" in html and "your stall" not in html
    assert (
        f"/shops/{shop.pk}/" in html or reverse("shops:detail", args=[club.slug, shop.pk]) in html
    )
    page = login(player).get(wtb(club, item))
    assert b"<html" in page.content and b"Where to buy Rope" in page.content


def test_your_stall(login, club, player, item):
    make_stall(club, player, "Mine", item)
    r = login(player).get(wtb(club, item))
    assert b"your stall" in r.content


def test_closed_stall_and_held_junk_excluded(club, player, other_player, item):
    other = Character.objects.create(
        club=club, owner=Membership.objects.get(user=player, club=club), name="Pl"
    )
    make_stall(club, other_player, "Shut", item, open_=False)
    assert item.pk not in available_item_ids(club, TODAY)
    ch = make_stall(club, other_player, "Held", item)
    assert item.pk in available_item_ids(club, TODAY)
    trade = Trade.objects.create(
        club=club, sender=ch, receiver=other, status=Trade.Status.REQUESTED
    )
    TradeLine.objects.create(trade=trade, item=item, quantity=1, from_sender=True)
    quantities, _ = _stall_quantities(club)
    assert (ch.pk, item.pk) not in quantities


def test_empty_state(login, club, player, item):
    r = login(player).get(wtb(club, item))
    assert b"Not for sale anywhere today." in r.content


def test_cross_club_isolation(login, club, other_club, player, other_player, item):
    other_item = Item.objects.create(club=other_club, name="Foreign")
    shop = make_shop(other_club, name="Elsewhere")
    ShopStock.objects.create(shop=shop, item=other_item, quantity=1)
    assert login(player).get(wtb(club, other_item)).status_code == 404
    # same item id in a different club URL slug is not reachable either
    assert login(player).get(
        reverse("items:where_to_buy", args=[other_club.slug, other_item.pk])
    ).status_code in (403, 404)
    r = login(player).get(wtb(club, other_item.__class__.objects.get(pk=item.pk)))
    assert b"Elsewhere" not in r.content
    assert other_item.pk not in available_item_ids(club, TODAY)


def test_stall_parity_with_listed_rows(club, player, other_player, item):
    other = Item.objects.create(club=club, name="Other", value_cp=5)
    a = make_stall(club, player, "A", item, mark=5, have=3)
    b = make_stall(club, other_player, "B", other, mark=1, have=4)
    JunkMark.objects.create(character=b, item=item, quantity=2)  # owns none
    quantities, _ = _stall_quantities(club)
    for ch in (a, b):
        expected = {r.item.pk: r.quantity for r in listed_rows(ch)}
        got = {i: q for (c, i), q in quantities.items() if c == ch.pk}
        assert got == expected


def _queries(fn):
    with CaptureQueriesContext(connection) as ctx:
        fn()
    return len(ctx)


def test_query_count_flat(login, club, player, other_player, item):
    c = login(player)
    shop = make_shop(club)
    ShopStock.objects.create(shop=shop, item=item, quantity=1)
    make_stall(club, other_player, "S0", item)
    c.get(index(club))
    base_index = _queries(lambda: c.get(index(club)))
    base_wtb = _queries(lambda: c.get(wtb(club, item)))
    for n in range(4):
        it = Item.objects.create(club=club, name=f"I{n}", value_cp=n)
        sh = make_shop(club, name=f"Shop{n}")
        ShopStock.objects.create(shop=sh, item=it, quantity=1)
        ShopStock.objects.create(shop=sh, item=item, quantity=1)
        make_stall(club, other_player, f"Stall{n}", item)
        make_stall(club, other_player, f"X{n}", it)
    assert _queries(lambda: c.get(index(club))) == base_index
    assert _queries(lambda: c.get(wtb(club, item))) <= base_wtb + 0


def test_demo_has_shop_and_stall_item(club):
    call_command("seed_demo")
    call_command("seed_demo")
    demo = Club.objects.exclude(pk=club.pk).first()
    ids = set(ShopStock.objects.filter(shop__club=demo).values_list("item_id", flat=True))
    stalls, _ = _stall_quantities(demo)
    assert stalls
    assert available_item_ids(demo, timezone.localdate()) & ids
    stall_items = {i for _, i in stalls}
    assert any(
        where_to_buy(demo, Item.objects.get(pk=i), timezone.localdate(), None).stalls
        for i in stall_items
    )
