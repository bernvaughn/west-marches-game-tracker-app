
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from ledger.models import LedgerEntry

pytestmark = [pytest.mark.django_db, pytest.mark.story("U33")]
HX = {"HTTP_HX_REQUEST": "true"}


def url(club, shop, stock):
    return reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])


def purchases():
    return LedgerEntry.objects.filter(kind="purchase")


def test_htmx_get_returns_fragment(club, shop, always_open, stock, rich_character, player, login):
    resp = login(player).get(url(club, shop, stock), **HX)
    body = resp.content.decode()
    assert resp.status_code == 200
    assert "<html" not in body
    assert "modal-header" in body
    assert stock.item.name in body
    assert "Buying as <strong>Aria" in body
    assert "Coins before" in body and "Coins after" in body
    assert 'name="quantity"' in body
    assert "HX-Request" in resp["Vary"]


def test_htmx_get_quantity_recomputes(
    club, shop, always_open, stock, rich_character, player, login
):
    one = login(player).get(url(club, shop, stock), **HX).content.decode()
    two = login(player).get(url(club, shop, stock) + "?quantity=2", **HX).content.decode()
    assert one != two
    assert 'value="2"' in two


def test_plain_get_is_full_page(club, shop, always_open, stock, rich_character, player, login):
    body = login(player).get(url(club, shop, stock)).content.decode()
    assert "<html" in body
    assert "Buying as <strong>Aria" in body


def test_htmx_confirm_closes_modal_and_refreshes(
    club, shop, always_open, stock, rich_character, player, login
):
    resp = login(player).post(url(club, shop, stock), {"quantity": 1}, **HX)
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == reverse("shops:detail", args=[club.slug, shop.pk])
    assert purchases().count() == 1
    stock.refresh_from_db()
    assert stock.quantity == 1


@pytest.mark.story("U33")
def test_htmx_buy_message_shown_after_redirect(
    club, shop, always_open, stock, rich_character, player, login
):
    c = login(player)
    resp = c.post(url(club, shop, stock), {"quantity": 1}, **HX)
    assert "Bought" in c.get(resp["HX-Redirect"]).content.decode()


def test_plain_post_redirects(club, shop, always_open, stock, rich_character, player, login):
    resp = login(player).post(url(club, shop, stock), {"quantity": 1})
    assert resp.status_code == 302


def test_already_sold_rerenders(club, shop, always_open, stock, rich_character, player, login):
    stock.quantity = 0
    stock.save()
    resp = login(player).post(url(club, shop, stock), {"quantity": 1}, **HX)
    assert resp.status_code == 200
    assert "Already sold" in resp.content.decode()
    assert purchases().count() == 0


def test_cannot_afford_rerenders(club, shop, always_open, stock, character, player, login):
    resp = login(player).post(url(club, shop, stock), {"quantity": 1}, **HX)
    assert resp.status_code == 200
    assert "cannot afford" in resp.content.decode()
    assert purchases().count() == 0
    stock.refresh_from_db()
    assert stock.quantity == 2


def test_no_character_no_submit(club, shop, always_open, stock, player, login):
    body = login(player).get(url(club, shop, stock), **HX).content.decode()
    assert "You have no character in this club." in body
    assert 'type="submit"' not in body


def test_cross_club_isolation(club, shop, always_open, stock, other_club, login):
    outsider = get_user_model().objects.create_user(
        "out@example.com", password="pw", display_name="Out"
    )
    resp = login(outsider).get(url(club, shop, stock), **HX)
    assert resp.status_code == 404
    assert stock.item.name not in resp.content.decode()


def test_stock_buy_link_and_trigger(club, shop, always_open, stock, rich_character, player, login):
    body = login(player).get(reverse("shops:detail", args=[club.slug, shop.pk])).content.decode()
    assert f'href="{url(club, shop, stock)}"' in body
    assert f'hx-get="{url(club, shop, stock)}"' in body
    assert "data-app-modal" in body
    assert "shopStockChanged from:body" in body
