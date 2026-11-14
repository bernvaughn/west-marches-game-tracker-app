from datetime import date

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from ledger.coins import format_coins
from shops.models import Rotation, Shop

pytestmark = pytest.mark.django_db


def url(name, club, *args):
    return reverse(f"shops:{name}", args=[club.slug, *args])


@pytest.fixture
def other_open(other_club, other_shop):
    r = Rotation.objects.create(club=other_club, name="Always", open_date=date(2000, 1, 1))
    r.shops.add(other_shop)
    return other_shop


@pytest.mark.story("C1")
def test_index_lists_open_only(login, player, club, shop, always_open, closed_shop):
    body = login(player).get(url("index", club)).content.decode()
    assert "Lantern" in body
    assert "Shuttered" not in body


@pytest.mark.story("C1")
def test_index_empty_state(login, player, club, shop):
    body = login(player).get(url("index", club)).content.decode()
    assert "No shops are open today." in body


@pytest.mark.story("C1")
def test_detail_shows_price_and_quantity(login, player, club, shop, always_open, stock):
    body = login(player).get(url("detail", club, shop.id)).content.decode()
    assert format_coins(100) in body
    assert "Rope" in body
    assert ">2<" in body
    assert "Sell to" not in body
    assert url("buy", club, shop.id, stock.id) in body


@pytest.mark.story("C1")
def test_cross_club_404(login, player, club, other_open):
    c = login(player)
    assert c.get(url("detail", club, other_open.id)).status_code == 404
    assert c.get(url("stock_fragment", club, other_open.id)).status_code == 404


@pytest.mark.story("C4")
def test_wrapper_polls_when_visible(login, player, club, shop, always_open):
    body = login(player).get(url("detail", club, shop.id)).content.decode()
    assert f'hx-get="{url("stock_fragment", club, shop.id)}"' in body
    assert "every 5s [document.visibilityState === 'visible']" in body
    assert "visibilitychange[document.visibilityState === 'visible'] from:document" in body


@pytest.mark.story("C4")
def test_sold_out_disappears(login, player, club, shop, always_open, stock):
    c = login(player)
    assert "Rope" in c.get(url("stock_fragment", club, shop.id)).content.decode()
    type(stock).objects.filter(pk=stock.pk).update(quantity=0)
    assert "Rope" not in c.get(url("stock_fragment", club, shop.id)).content.decode()


@pytest.mark.story("C4")
def test_retired_hidden_and_fragment_has_no_inputs(
    login, player, club, shop, always_open, stock, item
):
    item.retired = True
    item.save()
    body = login(player).get(url("stock_fragment", club, shop.id)).content.decode()
    assert "Rope" not in body
    stock.item.retired = False
    stock.item.save()
    body = login(player).get(url("stock_fragment", club, shop.id)).content.decode()
    assert "Rope" in body
    for tag in ("<input", "<form", "<select", "<textarea", "<html"):
        assert tag not in body


@pytest.mark.story("U9")
def test_unlimited_and_limited(login, player, club, shop, always_open, stock, unlimited_stock):
    body = login(player).get(url("stock_fragment", club, shop.id)).content.decode()
    assert "Unlimited" in body
    assert ">2<" in body


@pytest.mark.story("U10")
def test_look(login, player, club, shop, always_open):
    Shop.objects.filter(pk=shop.pk).update(
        color="ember", symbol="🔥", keeper_description="Gruff but fair."
    )
    c = login(player)
    body = c.get(url("detail", club, shop.id)).content.decode()
    assert "wm-shop-banner--ember" in body
    assert "🔥" not in body  # B-16: no stray symbol beside the heading
    assert "Marta" in body
    assert "Gruff but fair." in body
    index = c.get(url("index", club)).content.decode()
    assert "wm-shop-card--ember" in index
    assert "🔥" in index


@pytest.mark.story("U10")
def test_css_has_all_colors():
    css = open(finders.find("css/areas/catalogue.css")).read()
    for color in Shop.Color.values:
        assert f".wm-shop-banner--{color}" in css
        assert f".wm-shop-card--{color}" in css


@pytest.mark.story("U36")
def test_detail_banner_silhouette_and_keeper(login, player, club, shop, always_open):
    Shop.objects.filter(pk=shop.pk).update(silhouette="dwarf_smith")
    body = login(player).get(url("detail", club, shop.id)).content.decode()
    assert "wm-shop-banner" in body
    assert "shops/silhouettes/dwarf_smith.svg" in body
    assert '<figcaption class="wm-shop-keeper-name">Marta</figcaption>' in body
    assert "Sell to" not in body


@pytest.mark.story("U36")
def test_detail_without_keeper(login, player, club, shop, always_open):
    Shop.objects.filter(pk=shop.pk).update(keeper_name="")
    body = login(player).get(url("detail", club, shop.id)).content.decode()
    assert "shops/silhouettes/hooded_trader.svg" in body
    assert "wm-shop-keeper-name" not in body


@pytest.mark.story("C1")
def test_closed_shop(login, player, club_admin, site_admin, club, closed_shop):
    p = login(player)
    assert p.get(url("detail", club, closed_shop.id)).status_code == 404
    assert p.get(url("stock_fragment", club, closed_shop.id)).status_code == 404
    for user in (club_admin, site_admin):
        c = login(user)
        r = c.get(url("detail", club, closed_shop.id))
        assert r.status_code == 200
        assert "Closed" in r.content.decode()
        assert c.get(url("stock_fragment", club, closed_shop.id)).status_code == 200


@pytest.mark.story("C1")
def test_open_shop_no_banner(login, player, club, shop, always_open):
    body = login(player).get(url("detail", club, shop.id)).content.decode()
    assert "shop-closed-banner" not in body
