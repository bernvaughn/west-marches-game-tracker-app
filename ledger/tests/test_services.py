import datetime

import pytest

from ledger.models import LedgerEntry
from ledger.services import (
    InsufficientFunds,
    InsufficientItems,
    LedgerError,
    Line,
    available_coins,
    available_items,
    coin_balance,
    held_coins,
    held_items,
    item_quantities,
    record,
    record_many,
)

pytestmark = [pytest.mark.story("FOUNDATION"), pytest.mark.django_db]


def test_empty_balance(character):
    assert coin_balance(character) == 0
    assert item_quantities(character) == {}


def test_balance_and_quantities_are_sums(character, item, second_item):
    record(character, "award", [Line(coins=500), Line(item=item, quantity=3)])
    record(character, "purchase", [Line(coins=-200), Line(item=item, quantity=-1)])
    record(character, "award", [Line(item=second_item, quantity=2)])
    record(character, "consumed", [Line(item=second_item, quantity=-2)])
    assert coin_balance(character) == 300
    assert item_quantities(character) == {item.pk: 2}


def test_held_coins_and_items_are_zero(character):
    assert held_coins(character) == 0
    assert held_items(character) == {}


def test_available_equals_balance(character, item):
    record(character, "award", [Line(coins=500), Line(item=item, quantity=3)])
    assert available_coins(character) == coin_balance(character)
    assert available_items(character) == item_quantities(character)


def test_insufficient_funds_writes_nothing(funded):
    before = LedgerEntry.objects.count()
    with pytest.raises(InsufficientFunds):
        record(funded, "purchase", [Line(coins=-1001)])
    assert LedgerEntry.objects.count() == before


def test_insufficient_items_writes_nothing(funded, item):
    before = LedgerEntry.objects.count()
    with pytest.raises(InsufficientItems):
        record(funded, "consumed", [Line(item=item, quantity=-6)])
    assert LedgerEntry.objects.count() == before


def test_positive_does_not_fund_negative_in_same_entry(character):
    with pytest.raises(InsufficientFunds):
        record(character, "sale", [Line(coins=100), Line(coins=-100)])


def test_date_actor_and_extras(character, game_master, item):
    e = record(character, "award", [Line(coins=1)])
    assert e.date == datetime.date.today() or e.date  # default set
    d = datetime.date(2026, 1, 2)
    e2 = record(
        character, "award", [Line(coins=1)], note="n", date=d, actor=game_master, via_agent=True
    )
    assert (e2.date, e2.note, e2.created_by, e2.via_agent) == (d, "n", game_master, True)
    rev = record(character, "reversal", [Line(coins=-1)], reverses=e)
    assert rev.reverses == e


def test_validation_errors(character, other_club, item):
    from items.models import Item

    with pytest.raises(LedgerError):
        record(character, "award", [])
    with pytest.raises(LedgerError):
        record(character, "bogus", [Line(coins=1)])
    with pytest.raises(LedgerError):
        record(character, "award", [Line()])
    with pytest.raises(LedgerError):
        record(character, "award", [Line(item=item, quantity=0)])
    foreign = Item.objects.create(club=other_club, name="X")
    with pytest.raises(LedgerError):
        record(character, "award", [Line(item=foreign, quantity=1)])
    assert LedgerEntry.objects.count() == 0


def test_record_many_all_or_nothing(funded, other_character):
    before = LedgerEntry.objects.count()
    with pytest.raises(InsufficientFunds):
        record_many(
            [
                dict(character=other_character, kind="award", lines=[Line(coins=10)]),
                dict(character=funded, kind="purchase", lines=[Line(coins=-5000)]),
            ]
        )
    assert LedgerEntry.objects.count() == before
    with pytest.raises(LedgerError):
        record_many(
            [
                dict(character=other_character, kind="award", lines=[Line(coins=10)]),
                dict(character=funded, kind="award", lines=[]),
            ]
        )
    assert LedgerEntry.objects.count() == before


def test_record_many_writes_all(funded, other_character):
    entries = record_many(
        [
            dict(character=funded, kind="purchase", lines=[Line(coins=-100)]),
            dict(character=other_character, kind="award", lines=[Line(coins=100)]),
        ]
    )
    assert len(entries) == 2
    assert coin_balance(other_character) == 100


def test_record_many_sums_negatives_per_character(funded):
    with pytest.raises(InsufficientFunds):
        record_many(
            [
                dict(character=funded, kind="purchase", lines=[Line(coins=-600)]),
                dict(character=funded, kind="purchase", lines=[Line(coins=-600)]),
            ]
        )
