import datetime

import pytest
from django.core.management import call_command

from accounts.demo import DEMO_LOGINS, DEMO_PASSWORD
from accounts.models import Club, Membership, User
from items.models import Item
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import coin_balance
from map.models import HexMap, Location, Tile, TileVisit, XPLevel
from player_characters.models import Character
from quests.models import Quest, QuestRequirement, QuestReward
from shops.models import Rotation, Shop, ShopStock

pytestmark = [pytest.mark.story("FOUNDATION"), pytest.mark.django_db]

MODELS = [
    User,
    Club,
    Membership,
    Character,
    Item,
    Shop,
    ShopStock,
    Rotation,
    Quest,
    QuestRequirement,
    QuestReward,
    HexMap,
    Tile,
    Location,
    TileVisit,
    XPLevel,
    LedgerEntry,
    LedgerLine,
]


def counts():
    return [m.objects.count() for m in MODELS]


def test_seed_twice_is_idempotent(capsys):
    call_command("seed_demo")
    first = counts()
    assert all(first)
    call_command("seed_demo")
    assert counts() == first
    out = capsys.readouterr().out
    assert DEMO_PASSWORD in out
    for email, _ in DEMO_LOGINS:
        assert email in out


def test_balances_and_shops():
    call_command("seed_demo")
    assert coin_balance(Character.objects.get(name="Aria Windrunner")) == 5000
    assert coin_balance(Character.objects.get(name="Borin Stonefist")) == 2000
    today = datetime.date.today()
    rotations = Rotation.objects.all()
    assert rotations.filter(close_date__isnull=True, open_date__lte=today).exists()
    assert rotations.filter(close_date__gte=today, open_date__lte=today).exists()
    assert ShopStock.objects.filter(quantity__isnull=True).exists()
    assert ShopStock.objects.filter(quantity__isnull=False).exists()


@pytest.mark.parametrize("email", [e for e, _ in DEMO_LOGINS])
def test_demo_logins(client, email):
    call_command("seed_demo")
    assert client.login(username=email, password=DEMO_PASSWORD)
    assert client.get("/c/demo/").status_code == 200
