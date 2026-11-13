from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse

from items.models import Item
from ledger.services import Line, record
from shops.models import Rotation, Shop

pytestmark = pytest.mark.django_db

CSS = Path(__file__).resolve().parents[2] / "static/css/areas/shops.css"


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return shop


@pytest.mark.story("U77")
def test_sign_never_positioned_over_building():
    screen = CSS.read_text().split("@media print")[0]
    sign_rules = [r for r in screen.split("}") if ".wm-street-sign" in r.split("{")[0]]
    assert sign_rules and all("position: absolute" not in r for r in sign_rules)
    assert "position: static" in sign_rules[0]
    assert "top:" not in sign_rules[0]


@pytest.mark.story("U77")
def test_manage_list_columns(club_admin, login, club, shop):
    shop.street_position = 3
    shop.save()
    body = login(club_admin).get(reverse("shops:manage_list", args=[club.slug])).content.decode()
    heads = [
        "Name",
        "Street position",
        "Shopkeeper",
        "Sell %",
        "Buy %",
        "Symbol",
        "Status",
        "Stock",
    ]
    pos = [body.index(f"{h}</th>") for h in heads]
    assert pos == sorted(pos)
    assert "Marta" in body and "100%" in body and "50%" in body and ">3</td>" in body


@pytest.mark.story("U77")
def test_your_inventory_icons_and_outline_sell(login, player, club, open_shop, character):
    gem = Item.objects.create(club=club, name="Gem", value_cp=300, symbol="💎")
    record(character, "award", [Line(item=gem, quantity=1)])
    b = login(player).get(reverse("shops:detail", args=[club.slug, open_shop.id])).content.decode()
    c = b[b.index('id="your-inventory"') :]
    assert "wm-item-symbol" in c and "btn-outline-secondary" in c
    assert "btn-primary" not in c


@pytest.mark.story("U77")
def test_demo_shops_have_descriptions_idempotent(db):
    call_command("seed_demo")
    call_command("seed_demo")
    shops = Shop.objects.filter(name__in=["The Rusty Lantern", "Wandering Caravan"])
    assert shops.count() == 2
    assert all(s.description for s in shops)


@pytest.mark.story("U77")
def test_no_description_no_button(login, player, club, open_shop):
    b = login(player).get(reverse("shops:detail", args=[club.slug, open_shop.id])).content.decode()
    assert "wm-shop-about-toggle" not in b
    open_shop.description = "Hello"
    open_shop.save()
    b = login(player).get(reverse("shops:detail", args=[club.slug, open_shop.id])).content.decode()
    assert "wm-shop-about-toggle" in b
