from datetime import date

import pytest
from django.contrib.staticfiles import finders
from django.urls import NoReverseMatch, reverse

from ledger.services import Line, record
from player_characters.junk import set_junk
from shops.models import Rotation, Shop

pytestmark = [pytest.mark.django_db, pytest.mark.story("U63")]


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    Shop.objects.filter(pk=shop.pk).update(
        description="Fine wares.", keeper_description="Gruff but fair.", symbol="⚒"
    )
    shop.refresh_from_db()
    return shop


@pytest.fixture
def loot(character, item):
    record(character, "award", [Line(item=item, quantity=3)])
    return item


def page(login, player, club, shop):
    return login(player).get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()


def test_no_old_sell_route_or_button(login, player, club, open_shop, loot):
    with pytest.raises(NoReverseMatch):
        reverse("shops:sell", args=[club.slug, open_shop.id])
    assert "Sell to" not in page(login, player, club, open_shop)


def test_inventory_row_sells_through_sell_item(login, player, club, open_shop, loot, character):
    html = page(login, player, club, open_shop)
    url = reverse("shops:sell_item", args=[club.slug, open_shop.id, loot.id])
    assert f'hx-post="{url}"' in html
    assert 'name="quantity"' in html and "wm-sell-form" in html and 'aria-label="Sell ' in html


def test_no_sell_forms_when_closed(login, player, club, shop, loot, character, closed_shop):
    html = page(login, player, club, shop)
    assert "wm-sell-form" not in html


def test_sell_junk_still_renders(login, player, club, open_shop, loot, character):
    set_junk(character, loot, 1, player)
    assert "Sell junk" in page(login, player, club, open_shop)


def test_title_row(login, player, club, open_shop):
    html = page(login, player, club, open_shop)
    assert "wm-shop-title-row" not in html
    assert html.index("wm-page-header") < html.index("<h1") < html.index("wm-shop-banner ")
    assert html.count("<h1") == 1


def test_icon_buttons(login, player, club, open_shop):
    html = page(login, player, club, open_shop)
    for label in ("Shop description", "Leave the shop"):
        assert f'aria-label="{label}"' in html
        assert f'title="{label}" data-wm-tooltip' in html


def test_keeper_button_and_both_boxes_without_js(login, player, club, open_shop):
    html = page(login, player, club, open_shop)
    assert 'class="wm-shop-keeper-name wm-shop-keeper-toggle" aria-controls="keeper-about"' in html
    assert 'aria-controls="shop-about"' in html
    before = html.split('id="stock"', 1)[0]
    shop_box = before[before.index('id="shop-about"') : before.index('id="keeper-about"')]
    keeper_box = before[before.index('id="keeper-about"') :]
    assert "Fine wares." in shop_box and "Gruff" not in shop_box
    assert "Gruff but fair." in keeper_box and "Fine wares." not in keeper_box


def test_js_toggles_one_box_at_a_time():
    js = open(finders.find("js/shop_banner.js")).read()
    assert "[aria-controls]" in js and "aria-expanded" in js
    assert "show(p.box.hidden ? p : null)" in js


def test_sell_form_does_not_inherit_inventory_swap(login, player, club, open_shop, loot, character):
    html = page(login, player, club, open_shop)
    start = html.index('class="wm-inline-form wm-sell-form wm-row-actions"')
    form = html[html.rindex("<form", 0, start) : start]
    assert 'hx-select="unset"' in form and 'hx-swap="innerHTML"' in form
