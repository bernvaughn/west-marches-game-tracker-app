from datetime import date

import pytest
from django.core.management import call_command
from django.urls import resolve, reverse

from items.models import Item
from shops import buying
from shops.models import Rotation, Shop, ShopStock
from shops.services import AlreadySold, NotStocked, ShopClosed, ShopError, is_open, open_shops
from shops.views import browse, manage, rotations
from shops.views import buy as buy_views
from shops.views import sell as sell_views

pytestmark = [pytest.mark.story("FOUNDATION"), pytest.mark.django_db]

VIEWS = {
    "index": browse.index,
    "detail": browse.shop_detail,
    "stock_fragment": browse.stock_fragment,
    "buy": buy_views.buy,
    "sell": sell_views.sell,
    "manage_list": manage.shop_list,
    "manage_create": manage.shop_create,
    "manage_edit": manage.shop_edit,
    "stock_add": manage.stock_add,
    "stock_edit": manage.stock_edit,
    "stock_remove": manage.stock_remove,
    "rotation_list": rotations.rotation_list,
    "rotation_create": rotations.rotation_create,
    "rotation_edit": rotations.rotation_edit,
    "rotation_delete": rotations.rotation_delete,
}
MEMBER = ["index", "detail", "stock_fragment", "buy", "sell"]
ADMIN_GET = [
    "manage_list", "manage_create", "manage_edit", "stock_add", "stock_edit",
    "rotation_list", "rotation_create", "rotation_edit",
]  # fmt: skip
ADMIN_POST = ["stock_remove", "rotation_delete"]


def url(name, club, shop, stock, rotation):
    kwargs = {"club_slug": club.slug}
    if name in {"detail", "stock_fragment", "buy", "sell", "manage_edit", "stock_add",
                "stock_edit", "stock_remove"}:  # fmt: skip
        kwargs["shop_id"] = shop.pk
    if name in {"buy", "stock_edit", "stock_remove"}:
        kwargs["stock_id"] = stock.pk
    if name in {"rotation_edit", "rotation_delete"}:
        kwargs["rotation_id"] = rotation.pk
    return reverse(f"shops:{name}", kwargs=kwargs)


@pytest.fixture
def ctx(club, shop, stock, always_open):
    return club, shop, stock, always_open


def get(client, name, ctx):
    return client.get(url(name, *ctx)) if name not in ADMIN_POST else client.post(url(name, *ctx))


def test_urls_resolve(ctx):
    for name, view in VIEWS.items():
        assert resolve(url(name, *ctx)).func is view


def test_member_urls_ok(login, player, ctx):
    for name in MEMBER:
        assert get(login(player), name, ctx).status_code == 200


@pytest.mark.parametrize("who", ["club_admin", "site_admin"])
def test_admin_urls_ok(request, login, ctx, who):
    client = login(request.getfixturevalue(who))
    for name in ADMIN_GET:
        assert client.get(url(name, *ctx)).status_code == 200
    for name in ADMIN_POST:
        assert client.post(url(name, *ctx)).status_code == 302


@pytest.mark.parametrize("who", ["player", "game_master"])
def test_admin_urls_forbidden(request, login, ctx, who):
    client = login(request.getfixturevalue(who))
    for name in ADMIN_GET:
        assert client.get(url(name, *ctx)).status_code == 403
    for name in ADMIN_POST:
        assert client.post(url(name, *ctx)).status_code == 403
        assert client.get(url(name, *ctx)).status_code == 403


def test_non_member_gets_404(login, player, other_club, other_shop):
    stock = ShopStock.objects.create(
        shop=other_shop, item=Item.objects.create(club=other_club, name="X"), quantity=1
    )
    rotation = Rotation.objects.create(club=other_club, name="R", open_date=date(2000, 1, 1))
    for name in VIEWS:
        r = login(player).generic(
            "POST" if name in ADMIN_POST else "GET",
            url(name, other_club, other_shop, stock, rotation),
        )
        assert r.status_code == 404, name


def test_cross_club_ids_404(login, club_admin, club, ctx, other_club, other_shop):
    other_stock = ShopStock.objects.create(
        shop=other_shop, item=Item.objects.create(club=other_club, name="X"), quantity=1
    )
    other_rot = Rotation.objects.create(club=other_club, name="R", open_date=date(2000, 1, 1))
    _, shop, stock, rotation = ctx
    sibling = Shop.objects.create(club=club, name="Sibling")
    sibling_stock = ShopStock.objects.create(shop=sibling, item=stock.item, quantity=1)
    client = login(club_admin)
    shop_names = ["detail", "stock_fragment", "sell", "manage_edit", "stock_add"]
    stock_names = ["buy", "stock_edit", "stock_remove"]
    rot_names = ["rotation_edit", "rotation_delete"]
    checks = [(n, other_shop, stock, rotation) for n in shop_names + stock_names]
    checks += [(n, shop, other_stock, rotation) for n in stock_names]
    checks += [(n, shop, sibling_stock, rotation) for n in stock_names]  # other shop, same club
    checks += [(n, shop, stock, other_rot) for n in rot_names]
    for name, s, st, rot in checks:
        method = "POST" if name in ADMIN_POST else "GET"
        r = client.generic(method, url(name, club, s, st, rot))
        assert r.status_code == 404, (name, s, st, rot)


def test_is_open_matches_open_shops(club, shop, closed_shop):
    rot = Rotation.objects.create(
        club=club, name="W", open_date=date(2026, 3, 10), close_date=date(2026, 3, 20)
    )
    rot.shops.add(shop)
    for d in [date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 20), date(2026, 3, 21)]:
        for s in (shop, closed_shop):
            assert is_open(s, d) == open_shops(club, d).filter(pk=s.pk).exists()
    assert is_open(shop, date(2026, 3, 15))
    assert not is_open(shop, date(2026, 3, 21))
    assert not is_open(closed_shop, date(2026, 3, 15))


def test_is_open_no_close_date(shop, always_open):
    assert is_open(shop, date(2099, 1, 1))


def test_nav_for_roles(login, player, club_admin, site_admin, club):
    link = "Manage shops"
    assert link not in login(player).get(reverse("shops:index", args=[club.slug])).content.decode()
    for user in (club_admin, site_admin):
        body = login(user).get(reverse("shops:index", args=[club.slug])).content.decode()
        assert link in body


def test_slice_stubs_raise(rich_character, stock, shop):
    with pytest.raises(NotImplementedError):
        buying.buy(rich_character, stock)


def test_exceptions():
    for exc in (ShopClosed, NotStocked, AlreadySold):
        assert issubclass(exc, ShopError)
        assert str(exc()) == exc.default_message
    assert str(ShopError("x")) == "x"


def test_seed_demo_twice_has_look(club):
    call_command("seed_demo")
    call_command("seed_demo")
    shops = Shop.objects.exclude(color=Shop.Color.PARCHMENT)
    assert shops.count() == 2
    for s in shops:
        assert s.symbol and s.keeper_description


def test_color_default_and_palette():
    assert Shop().color == "parchment"
    assert [c.value for c in Shop.Color] == [
        "parchment", "forest", "ember", "ocean", "violet", "slate",
    ]  # fmt: skip


def test_fixtures(rich_character, other_character, unlimited_stock, closed_shop, other_shop):
    from ledger.services import coin_balance

    assert coin_balance(rich_character) == 1000
    assert unlimited_stock.quantity is None
