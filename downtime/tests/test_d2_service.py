import random

import pytest

from downtime import services
from downtime.models import DowntimeEntry, DowntimeEntryItem, DowntimePointEntry, DowntimeResult
from ledger import services as ledger
from ledger.models import LedgerEntry

pytestmark = [pytest.mark.django_db, pytest.mark.story("D2")]


class FixedRng:
    def __init__(self, index):
        self.index = index

    def choices(self, population, weights=None, k=1):
        return [population[self.index]]


def fund(character, n=5):
    services.award(character, n)


def test_chances_match_weights(entries):
    result = services.chances(entries)
    assert [round(p, 1) for _, p in result] == [75.0, 25.0]


def test_spend_writes_point_entry_ledger_and_result(character, action, entries, player):
    fund(character)
    res = services.spend(character, action, player, FixedRng(0))
    assert res.entry == entries[0]
    assert services.balance(character) == 4
    spend = DowntimePointEntry.objects.get(kind="spend")
    assert spend.delta == -1 and spend.source == f"downtime_action:{action.pk}"
    assert ledger.coin_balance(character) == 10
    assert LedgerEntry.objects.get().note.startswith("Downtime:")
    assert DowntimeResult.objects.get() == res


def test_spend_gives_items(character, action, entries, item, player):
    DowntimeEntryItem.objects.create(entry=entries[0], item=item, quantity=2)
    fund(character)
    services.spend(character, action, player, FixedRng(0))
    assert ledger.item_quantities(character) == {item.pk: 2}


def test_nothing_entry_writes_no_ledger_entry(character, action, entries, player):
    fund(character)
    services.spend(character, action, player, FixedRng(1))
    assert not LedgerEntry.objects.exists()
    assert services.balance(character) == 4


def test_refuses_too_few_points(character, action, entries, player):
    with pytest.raises(services.InsufficientPoints):
        services.spend(character, action, player)
    assert not DowntimeResult.objects.exists()


@pytest.mark.parametrize("name", ["upcoming_action", "ended_action"])
def test_refuses_not_live(request, character, name, player):
    act = request.getfixturevalue(name)
    DowntimeEntry.objects.create(action=act, label="x")
    fund(character)
    with pytest.raises(services.DowntimeError):
        services.spend(character, act, player)
    assert services.balance(character) == 5


def test_refuses_no_entries(character, action, player):
    fund(character)
    with pytest.raises(services.DowntimeError):
        services.spend(character, action, player)


def test_refuses_cross_club(character, other_club_action, player):
    DowntimeEntry.objects.create(action=other_club_action, label="x")
    fund(character)
    with pytest.raises(services.DowntimeError):
        services.spend(character, other_club_action, player)


def test_pick_follows_weights(character, action, entries, player):
    fund(character, 400)
    rng = random.Random(7)
    counts = {e.pk: 0 for e in entries}
    for _ in range(400):
        counts[services.spend(character, action, player, rng).entry_id] += 1
    assert 250 < counts[entries[0].pk] < 350


def test_rolls_back_when_ledger_fails(character, action, entries, player, monkeypatch):
    fund(character)

    def boom(*a, **k):
        raise ledger.LedgerError("boom")

    monkeypatch.setattr("downtime.services.ledger_record", boom)
    with pytest.raises(ledger.LedgerError):
        services.spend(character, action, player, FixedRng(0))
    assert not DowntimePointEntry.objects.filter(kind="spend").exists()
    assert services.balance(character) == 5
