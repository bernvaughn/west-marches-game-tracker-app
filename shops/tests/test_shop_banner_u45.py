from datetime import date

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from shops.models import Rotation, Shop

pytestmark = pytest.mark.django_db


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    Shop.objects.filter(pk=shop.pk).update(
        description="Fine wares.", keeper_description="Gruff but fair."
    )
    shop.refresh_from_db()
    return shop


def body(client, club, shop):
    return client.get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()


@pytest.mark.story("U45")
def test_name_label_before_silhouette(login, player, club, open_shop):
    b = body(login(player), club, open_shop)
    fig = b[b.index("<figure") : b.index("</figure>")]
    assert fig.index("wm-shop-keeper-name") < fig.index("<img")


@pytest.mark.story("U45")
def test_toggle_attributes_and_order(login, player, club, open_shop):
    b = body(login(player), club, open_shop)
    start = b.index("<button", b.index("wm-shop-actions"))
    toggle = b[start : b.index("</button>", start)]
    assert 'aria-expanded="true"' in toggle and 'aria-controls="shop-about"' in toggle
    assert b.index("wm-shop-about-toggle") < b.index("wm-shop-sellbar")


@pytest.mark.story("U45")
def test_box_in_banner_visible_without_js_and_not_below_table(login, player, club, open_shop):
    b = body(login(player), club, open_shop)
    before, after = b.split('id="stock"', 1)
    box = before[before.index('id="shop-about"') :]
    assert "Fine wares." in box and "Gruff but fair." in box
    assert 'id="shop-about" class="wm-shop-about-box">' in before
    assert "Fine wares." not in after and "Gruff but fair." not in after


@pytest.mark.story("U45")
def test_no_box_or_toggle_without_descriptions(login, player, club, open_shop):
    Shop.objects.filter(pk=open_shop.pk).update(description="", keeper_description="")
    b = body(login(player), club, open_shop)
    assert "shop-about" not in b.replace("shop_banner.js", "")
    assert "wm-shop-about-toggle" not in b


@pytest.mark.story("U45")
def test_css_and_js_exist():
    css = open(finders.find("css/areas/catalogue.css")).read()
    assert ".wm-shop-about-box[hidden]" in css and '"about about"' in css
    assert finders.find("js/shop_banner.js")
