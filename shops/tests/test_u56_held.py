from datetime import date

import pytest
from django.urls import reverse

from shops.models import Rotation

pytestmark = pytest.mark.django_db
HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return shop


def card(client, club, shop):
    b = client.get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()
    return b[b.index('id="your-inventory"') :]


@pytest.mark.story("U56")
def test_card_hides_line_without_holds(login, player, club, open_shop, rich_character):
    c = card(login(player), club, open_shop)
    assert "In open trades" not in c and "Held" not in c and "0 cp" not in c


@pytest.mark.story("U56")
def test_card_shows_line_without_hold(login, player, club, open_shop, rich_character):
    c = card(login(player), club, open_shop)
    assert "In open trades" not in c
    assert "Held" not in c


@pytest.mark.story("U56")
@pytest.mark.parametrize("extra", [HX, {}])
def test_buy_modal_line(login, player, club, shop, always_open, stock, rich_character, extra):
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    body = login(player).get(url, **extra).content.decode()
    assert "In open trades" not in body and "Held" not in body


@pytest.mark.story("U56")
@pytest.mark.parametrize("extra", [HX, {}])
def test_buy_modal_line_without_hold(
    login, player, club, shop, always_open, stock, rich_character, extra
):
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    body = login(player).get(url, **extra).content.decode()
    assert "In open trades" not in body
