from datetime import date

import pytest

from accounts.models import Membership
from items.models import Item
from ledger.services import Line, record
from player_characters.models import Character
from shops.models import Rotation, Shop, ShopStock


@pytest.fixture
def shop(club):
    return Shop.objects.create(
        club=club, name="Lantern", keeper_name="Marta", sell_percent=100, buy_percent=50
    )


@pytest.fixture
def other_shop(other_club):
    return Shop.objects.create(club=other_club, name="Elsewhere")


@pytest.fixture
def always_open(club, shop):
    rotation = Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1))
    rotation.shops.add(shop)
    return rotation


@pytest.fixture
def stock(shop, item):
    return ShopStock.objects.create(shop=shop, item=item, quantity=2)


@pytest.fixture
def unlimited_stock(club, shop):
    torch = Item.objects.create(club=club, name="Torch", value_cp=10)
    return ShopStock.objects.create(shop=shop, item=torch, quantity=None)


@pytest.fixture
def rich_character(character):
    record(character, "award", [Line(coins=1000)])
    return character


@pytest.fixture
def other_character(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.fixture
def closed_shop(club):
    return Shop.objects.create(club=club, name="Shuttered")
