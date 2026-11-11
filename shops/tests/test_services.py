import datetime

import pytest

from shops.models import Rotation, Shop, ShopStock
from shops.services import buy_price, open_shops, percent_price, sell_price

pytestmark = pytest.mark.story("FOUNDATION")


@pytest.mark.parametrize(
    "value, pct, expected",
    [(100, 50, 50), (5, 50, 2), (1, 50, 1), (0, 50, 0), (199, 100, 199), (7, 0, 1)],
)
def test_percent_price(value, pct, expected):
    assert percent_price(value, pct) == expected


@pytest.fixture
def shop(club):
    return Shop.objects.create(club=club, name="S", sell_percent=120, buy_percent=40)


def test_sell_price(shop, item):
    stock = ShopStock.objects.create(shop=shop, item=item)
    assert sell_price(stock) == 120
    stock.sell_percent = 150
    assert sell_price(stock) == 150


def test_buy_price(shop, item):
    assert buy_price(shop, item) == 40
    stock = ShopStock.objects.create(shop=shop, item=item)
    assert buy_price(shop, item) == 40
    stock.buy_percent = 75
    stock.save()
    assert buy_price(shop, item) == 75


def d(day, month=1):
    return datetime.date(2030, month, day)


def rotate(club, shop, open_date, close_date=None):
    r = Rotation.objects.create(club=club, name="R", open_date=open_date, close_date=close_date)
    r.shops.add(shop)
    return r


def test_open_shops_dates(club, shop):
    rotate(club, shop, d(10), d(20))
    assert shop not in open_shops(club, d(9))
    assert shop in open_shops(club, d(10))
    assert shop in open_shops(club, d(20))
    assert shop not in open_shops(club, d(21))


def test_open_shops_no_close(club, shop):
    rotate(club, shop, d(10))
    assert shop not in open_shops(club, d(9))
    assert shop in open_shops(club, datetime.date(2099, 1, 1))


def test_open_shops_gap(club, shop):
    rotate(club, shop, d(1), d(5))
    rotate(club, shop, d(15), d(20))
    assert shop not in open_shops(club, d(10))


def test_open_shops_distinct(club, shop):
    rotate(club, shop, d(1), d(20))
    rotate(club, shop, d(5))
    assert list(open_shops(club, d(10))) == [shop]


def test_open_shops_other_club(club, other_club):
    other = Shop.objects.create(club=other_club, name="O")
    rotate(other_club, other, d(1))
    assert not open_shops(club, d(10)).exists()
