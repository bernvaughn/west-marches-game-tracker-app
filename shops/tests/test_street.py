import re
from datetime import date
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.urls import reverse

from shops.models import Rotation, Shop

pytestmark = [pytest.mark.django_db, pytest.mark.story("U49")]

BUILDINGS = Path(__file__).resolve().parent.parent / "static" / "shops" / "buildings"
KEYS = [v for v, _ in Shop.Building.choices]


def street_url(club):
    return reverse("shops:index", args=[club.slug])


def open_shop(club, name, **kw):
    shop = Shop.objects.create(club=club, name=name, **kw)
    rotation, _ = Rotation.objects.get_or_create(
        club=club, name="Always", defaults={"open_date": date(2000, 1, 1)}
    )
    rotation.shops.add(shop)
    return shop


def street(body):
    return body[body.index('<ul class="wm-street"') :]


def test_order_by_position_name_id(login, player, club):
    open_shop(club, "Zed", street_position=1)
    open_shop(club, "Beta", street_position=2)
    open_shop(club, "Alpha", street_position=2)
    open_shop(club, "Alpha", street_position=2)
    open_shop(club, "First", street_position=0)
    body = login(player).get(street_url(club)).content.decode()
    names = re.findall(r'class="wm-street-name">([^<]+)<', body)
    assert names == ["First", "Zed", "Alpha", "Alpha", "Beta"]


def test_closed_and_cross_club_not_drawn(login, player, club, other_club):
    Shop.objects.create(club=club, name="Shuttered")
    open_shop(other_club, "Elsewhere")
    open_shop(club, "Lantern")
    body = login(player).get(street_url(club)).content.decode()
    assert "Lantern" in body
    assert "Shuttered" not in body and "Elsewhere" not in body


def test_lot_links_shows_name_symbol_building(login, player, club):
    shop = open_shop(club, "Lantern", symbol="🏮", building="smithy", color="ember")
    body = login(player).get(street_url(club)).content.decode()
    assert reverse("shops:detail", args=[club.slug, shop.id]) in body
    assert "🏮" in body and "Lantern" in body
    assert "shops/buildings/smithy.svg" in body
    assert "wm-shop-card--ember" in body


def test_same_html_every_load(login, player, club):
    open_shop(club, "A", street_position=3)
    open_shop(club, "B")
    client = login(player)
    first = client.get(street_url(club)).content.decode()
    second = client.get(street_url(club)).content.decode()
    assert street(first) == street(second)


def test_every_building_has_an_svg_and_no_strays():
    assert 8 <= len(KEYS) <= 10
    assert Shop._meta.get_field("building").default == "general_store"
    assert {p.name for p in BUILDINGS.iterdir()} == {f"{k}.svg" for k in KEYS}
    for key in KEYS:
        assert finders.find(f"shops/buildings/{key}.svg"), key
        text = (BUILDINGS / f"{key}.svg").read_text()
        assert 'viewBox="0 0 160 160"' in text and 'fill="currentColor"' in text
        assert not re.search(r"stroke|style=|class=|#[0-9a-fA-F]{3,6}", text), key


def test_street_position_default():
    assert Shop._meta.get_field("street_position").default == 0


def test_picker_and_save(login, club_admin, club, shop):
    client = login(club_admin)
    url = reverse("shops:manage_edit", kwargs={"club_slug": club.slug, "shop_id": shop.pk})
    body = client.get(url).content.decode()
    for key in KEYS:
        assert f"shops/buildings/{key}.svg" in body
    assert 'name="street_position"' in body
    data = {"name": "Lantern", "color": "parchment", "silhouette": "hooded_trader",
            "building": "tower", "street_position": "7", "symbol": "",
            "sell_percent": "100", "buy_percent": "50"}  # fmt: skip
    assert client.post(url, data).status_code == 302
    shop.refresh_from_db()
    assert (shop.building, shop.street_position) == ("tower", 7)


def test_base_links_shops_css_after_agent_css(login, player, club):
    body = login(player).get(street_url(club)).content.decode()
    assert body.index("css/areas/agent.css") < body.index("css/areas/shops.css")


def test_seed_demo_twice():
    call_command("seed_demo")
    call_command("seed_demo")
    shops = Shop.objects.all()
    assert shops.count() == 2
    assert len({s.building for s in shops}) == 2
    assert len({s.street_position for s in shops}) == 2
    assert all(s.street_position > 0 for s in shops)


def test_seed_demo_backfills_old_shops():
    call_command("seed_demo")
    Shop.objects.update(building="general_store", street_position=0)
    call_command("seed_demo")
    assert Shop.objects.get(name="The Rusty Lantern").building == "inn"
