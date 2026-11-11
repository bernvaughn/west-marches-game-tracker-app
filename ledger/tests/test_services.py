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
from player_characters.models import Trade

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


@pytest.mark.parametrize("status", [Trade.Status.REQUESTED, Trade.Status.ACCEPTED])
def test_open_trade_sender_lines_held(funded, item, open_trade, status):
    open_trade(status, lines=[dict(coins=300), dict(item=item, quantity=2)])
    assert held_coins(funded) == 300
    assert held_items(funded) == {item.pk: 2}
    assert available_coins(funded) == 700
    assert available_items(funded) == {item.pk: 3}


@pytest.mark.parametrize(
    "status", [Trade.Status.COMPLETED, Trade.Status.DECLINED, Trade.Status.CANCELLED]
)
def test_closed_trade_not_held(funded, open_trade, status):
    open_trade(status, lines=[dict(coins=300)])
    assert held_coins(funded) == 0


def test_receiver_give_side_held(funded, other_character, open_trade):
    open_trade(sender=other_character, receiver=funded, lines=[dict(from_sender=False, coins=400)])
    assert held_coins(funded) == 400
    assert held_coins(other_character) == 0


def test_exclude_trade_removes_one_hold(funded, open_trade):
    t1 = open_trade(lines=[dict(coins=300)])
    open_trade(lines=[dict(coins=100)])
    assert available_coins(funded) == 600
    assert available_coins(funded, exclude_trade=t1) == 900
    assert available_coins(funded, exclude_trade=t1.pk) == 900


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


def test_held_blocks_spend(funded, item, open_trade):
    open_trade(lines=[dict(item=item, quantity=4), dict(coins=900)])
    with pytest.raises(InsufficientItems):
        record(funded, "consumed", [Line(item=item, quantity=-2)])
    with pytest.raises(InsufficientFunds):
        record(funded, "purchase", [Line(coins=-200)])


def test_exclude_trade_allows_completion(funded, open_trade):
    trade = open_trade(lines=[dict(coins=900)])
    record(funded, "trade", [Line(coins=-900)], exclude_trade=trade)
    assert coin_balance(funded) == 100


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
            dict(character=funded, kind="trade", lines=[Line(coins=-100)]),
            dict(character=other_character, kind="trade", lines=[Line(coins=100)]),
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
