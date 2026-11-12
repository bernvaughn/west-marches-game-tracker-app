import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from shops.models import Rotation, Shop

pytestmark = pytest.mark.django_db

SVG_DIR = Path(__file__).resolve().parent.parent / "static" / "shops" / "silhouettes"


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return shop


def detail(client, club, shop):
    return client.get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()


def banner(body):
    return body[body.index('class="wm-shop-banner '):body.index('id="stock"')]


@pytest.mark.story("U39")
def test_silhouette_and_name_in_left_slot(login, player, club, open_shop):
    b = banner(detail(login(player), club, open_shop))
    fig = b.index("wm-shop-keeper-figure")
    assert fig < b.index("wm-shop-sellbar")
    figure = b[fig:b.index("</figure>")]
    assert "wm-shop-silhouette" in figure
    assert f"{open_shop.silhouette}.svg" in figure
    assert f'wm-shop-keeper-name">{open_shop.keeper_name}<' in figure


@pytest.mark.story("U39")
def test_banner_description_truncated(login, player, club, open_shop):
    Shop.objects.filter(pk=open_shop.pk).update(description=" ".join(f"w{i}" for i in range(40)))
    body = detail(login(player), club, open_shop)
    b = banner(body)
    assert "wm-shop-banner-about" in b and "w29" in b and "w30" not in b
    assert "wm-shop-about" in body.split('id="stock"')[1]  # long text kept in full below


@pytest.mark.story("U39")
def test_short_description_not_repeated_and_empty_plain(login, player, club, open_shop):
    c = login(player)
    Shop.objects.filter(pk=open_shop.pk).update(description="Fine wares.")
    body = detail(c, club, open_shop)
    assert "wm-shop-banner-about" in banner(body) and body.count("Fine wares.") == 1
    Shop.objects.filter(pk=open_shop.pk).update(description="")
    assert "wm-shop-banner-about" not in detail(c, club, open_shop)


@pytest.mark.story("U39")
def test_sell_button_keeps_place(login, player, club, open_shop):
    b = banner(detail(login(player), club, open_shop))
    sell = b[b.index("wm-shop-sellbar"):]
    assert f"Sell to {open_shop.keeper_name}" in sell


@pytest.mark.story("U39")
def test_every_key_has_a_file_and_no_strays():
    keys = set(Shop.Silhouette.values)
    assert len(keys) == 10
    assert all(finders.find(f"shops/silhouettes/{k}.svg") for k in keys)
    assert {p.stem for p in SVG_DIR.glob("*.svg")} == keys


@pytest.mark.story("U39")
@pytest.mark.parametrize("key", Shop.Silhouette.values)
def test_svg_one_style(key):
    text = (SVG_DIR / f"{key}.svg").read_text()
    root = ET.fromstring(text)
    assert root.get("viewBox") == "0 0 120 160" and root.get("fill") == "#2b2622"
    assert not re.findall(r'\b(?:stroke|style|class)=|fill="(?!#2b2622")', text)
    assert len(root) >= 2


@pytest.mark.story("U39")
def test_picker_lists_all_ten(login, club_admin, club, shop):
    body = login(club_admin).get(
        reverse("shops:manage_edit", args=[club.slug, shop.pk])
    ).content.decode()
    for key in Shop.Silhouette.values:
        assert f'value="{key}"' in body and f"shops/silhouettes/{key}.svg" in body


@pytest.mark.story("U39")
def test_other_club_player_cannot_open_banner(login, player, other_club, other_shop):
    r = login(player).get(reverse("shops:detail", args=[other_club.slug, other_shop.id]))
    assert r.status_code in (403, 404)
