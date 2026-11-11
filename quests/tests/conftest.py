from datetime import timedelta

import pytest
from django.utils import timezone

from items.models import Item
from ledger.services import Line, record
from quests.models import Quest, QuestRequirement, QuestReward


def _today():
    return timezone.localdate()


def _make(club, name, req_item, req_qty=1, coins=100, reward_item=None, **fields):
    quest = Quest.objects.create(club=club, name=name, **fields)
    QuestRequirement.objects.create(quest=quest, item=req_item, quantity=req_qty)
    QuestReward.objects.create(quest=quest, coins=coins)
    if reward_item:
        QuestReward.objects.create(quest=quest, item=reward_item, quantity=1)
    return quest


@pytest.fixture
def reward_item(club):
    return Item.objects.create(club=club, name="Healing potion", value_cp=5000)


@pytest.fixture
def quest(club, item, reward_item):
    return _make(
        club,
        "Pelts for the Tanner",
        item,
        req_qty=2,
        coins=1000,
        reward_item=reward_item,
        start_date=_today() - timedelta(days=7),
    )


@pytest.fixture
def upcoming_quest(club, item):
    return _make(club, "Upcoming quest", item, start_date=_today() + timedelta(days=1))


@pytest.fixture
def ended_quest(club, item):
    return _make(
        club,
        "Ended quest",
        item,
        start_date=_today() - timedelta(days=10),
        end_date=_today() - timedelta(days=1),
    )


@pytest.fixture
def limited_quest(club, item):
    return _make(
        club,
        "Limited quest",
        item,
        start_date=_today() - timedelta(days=1),
        max_completions=1,
        max_per_character=1,
    )


@pytest.fixture
def other_club_quest(other_club):
    other_item = Item.objects.create(club=other_club, name="Other rope", value_cp=100)
    return _make(other_club, "Other club quest", other_item)


@pytest.fixture
def give():
    def _give(character, item, qty):
        return record(character, "award", [Line(item=item, quantity=qty)], note="test award")

    return _give
