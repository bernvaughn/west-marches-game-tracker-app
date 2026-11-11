from unittest import mock

import pytest

from ledger.models import LedgerEntry
from ledger.services import Line, available_coins, available_items, coin_balance
from player_characters import trade_services as ts
from player_characters.models import Trade
from player_characters.trade_services import TradeError

pytestmark = pytest.mark.story("U16")


@pytest.fixture
def setup(character, other_character, item, give):
    give(character, item, 5, 1000)
    give(other_character, item, 3, 500)
    return character, other_character


def accepted(make_trade, s, r, lines=()):
    return make_trade(s, r, lines=lines, status="accepted")


def test_side_of_and_view(
    make_trade,
    character,
    other_character,
    player,
    other_player,
    game_master,
    club_admin,
    site_admin,
    club,
    other_club,
):
    t = make_trade(character, other_character)
    assert ts.side_of(t, player) == "sender"
    assert ts.side_of(t, other_player) == "receiver"
    assert ts.side_of(t, game_master) is None
    for u in (player, other_player, game_master, club_admin, site_admin):
        assert ts.can_view_trade(u, t)
    from accounts.models import Membership, User

    u = User.objects.create_user("x@example.com", password="pw", display_name="X")
    Membership.objects.create(user=u, club=club)
    assert not ts.can_view_trade(u, t)


def test_propose_happy(setup, item, player):
    c, o = setup
    t = ts.propose_trade(c, o, [Line(item=item, quantity=2), Line(coins=100)], "hi", player)
    assert t.status == "requested"
    assert len(ts.side_lines(t, "sender")) == 2
    assert ts.side_lines(t, "receiver") == []


def test_propose_rules(
    setup, item, player, other_player, foreign_character, foreign_item, character
):
    c, o = setup
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [Line(coins=1)], "", other_player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, foreign_character, [Line(coins=1)], "", player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, c, [Line(coins=1)], "", player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [], "  ", player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [Line(item=foreign_item, quantity=1)], "", player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [Line(coins=1001)], "", player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [Line(item=item, quantity=6)], "", player)
    assert ts.propose_trade(c, o, [], "note only", player)


def test_hold_blocks_second_offer(setup, item, player):
    c, o = setup
    ts.propose_trade(c, o, [Line(item=item, quantity=4), Line(coins=900)], "", player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [Line(item=item, quantity=2)], "", player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [Line(coins=200)], "", player)
    ts.propose_trade(c, o, [Line(item=item, quantity=1)], "", player)


def test_normalise(setup, item, player):
    c, o = setup
    t = ts.propose_trade(
        c,
        o,
        [
            Line(item=item, quantity=1),
            Line(item=item, quantity=2),
            Line(item=item, quantity=0),
            Line(coins=5),
            Line(coins=6),
        ],
        "",
        player,
    )
    lines = ts.side_lines(t, "sender")
    assert [(ln.item_id, ln.quantity, ln.coins) for ln in lines if ln.item_id] == [(item.pk, 3, 0)]
    assert [ln.coins for ln in lines if not ln.item_id] == [11]
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [Line(coins=-1)], "", player)
    with pytest.raises(TradeError):
        ts.propose_trade(c, o, [Line(item=item, quantity=1, coins=1)], "", player)


def test_accept(setup, make_trade, player, other_player, game_master):
    c, o = setup
    t = make_trade(c, o)
    for u in (player, game_master):
        with pytest.raises(TradeError):
            ts.accept_trade(t, u)
    ts.accept_trade(t, other_player)
    assert Trade.objects.get(pk=t.pk).status == "accepted"
    with pytest.raises(TradeError):
        ts.accept_trade(t, other_player)


def test_accept_blocked_by_other_accepted(
    setup, make_trade, third_character, other_player, game_master
):
    c, o = setup
    accepted(make_trade, c, o)
    t2 = make_trade(c, third_character)
    with pytest.raises(TradeError):
        ts.accept_trade(t2, game_master)
    # Several requests and several accepted received are fine.
    make_trade(c, o)
    r1 = make_trade(third_character, o)
    r2 = make_trade(c.club.characters.get(name="Cyra"), o)
    ts.accept_trade(r1, other_player)
    # r2 has same sender as r1 which is now accepted
    with pytest.raises(TradeError):
        ts.accept_trade(r2, other_player)


def test_set_side(setup, make_trade, item, player, other_player):
    c, o = setup
    t = make_trade(c, o)
    with pytest.raises(TradeError):
        ts.set_side(t, "receiver", [], other_player)
    t.status = "accepted"
    t.save()
    with pytest.raises(TradeError):
        ts.set_side(t, "receiver", [], player)
    ts.set_side(t, "receiver", [Line(item=item, quantity=1)], other_player)
    assert len(ts.side_lines(t, "receiver")) == 1
    with pytest.raises(TradeError):
        ts.set_side(t, "receiver", [Line(item=item, quantity=4)], other_player)


def test_set_side_own_holds_allowed_and_flags(setup, make_trade, item, player, other_player):
    c, o = setup
    t = accepted(make_trade, c, o, [(True, Line(item=item, quantity=5))])
    ts.set_side(t, "sender", [Line(item=item, quantity=5)], player)
    ts.set_side(t, "receiver", [Line(coins=10)], other_player)
    ts.approve_trade(t, "sender", player)
    t.refresh_from_db()
    assert t.sender_approved
    with pytest.raises(TradeError):
        ts.set_side(t, "sender", [Line(item=item, quantity=1)], player)
    # unchanged lines keep flags
    ts.set_side(t, "receiver", [Line(coins=10)], other_player)
    t.refresh_from_db()
    assert t.sender_approved
    # changed lines clear both
    ts.set_side(t, "receiver", [Line(coins=11)], other_player)
    t.refresh_from_db()
    assert not t.sender_approved and not t.receiver_approved


def test_approve_and_complete(setup, make_trade, item, player, other_player, game_master):
    c, o = setup
    t = accepted(make_trade, c, o, [(True, Line(item=item, quantity=2)), (False, Line(coins=300))])
    with pytest.raises(TradeError):
        ts.approve_trade(t, "sender", other_player)
    with pytest.raises(TradeError):
        ts.approve_trade(t, "sender", game_master)
    ts.approve_trade(t, "sender", player)
    with pytest.raises(TradeError):
        ts.approve_trade(t, "sender", player)
    t.refresh_from_db()
    assert t.status == "accepted"
    with mock.patch("player_characters.trade_services.record_many", wraps=ts.record_many) as m:
        ts.approve_trade(t, "receiver", other_player)
    assert m.call_count == 1
    t.refresh_from_db()
    assert t.status == "completed"
    entries = LedgerEntry.objects.filter(kind="trade")
    assert entries.count() == 2
    ce = entries.get(character=c)
    assert ce.note == "Trade with Bram"
    assert sorted((ln.item_id or 0, ln.quantity, ln.coins) for ln in ce.lines.all()) == sorted(
        [(item.pk, -2, 0), (0, 0, 300)]
    )
    oe = entries.get(character=o)
    assert oe.note == "Trade with Aria"
    assert sorted((ln.item_id or 0, ln.quantity, ln.coins) for ln in oe.lines.all()) == sorted(
        [(item.pk, 2, 0), (0, 0, -300)]
    )
    assert available_items(c)[item.pk] == 3
    assert coin_balance(o) == 200


def test_approve_empty_trade(setup, make_trade, player):
    c, o = setup
    t = accepted(make_trade, c, o)
    with pytest.raises(TradeError):
        ts.approve_trade(t, "sender", player)


def test_own_holds_do_not_block_completion(setup, make_trade, item, player, other_player):
    c, o = setup
    t = accepted(make_trade, c, o, [(True, Line(item=item, quantity=5)), (True, Line(coins=1000))])
    assert available_coins(c) == 1000 - 1000
    ts.approve_trade(t, "sender", player)
    ts.approve_trade(t, "receiver", other_player)
    t.refresh_from_db()
    assert t.status == "completed"


def test_complete_insufficient_clears_flags(setup, make_trade, player, other_player):
    from ledger.services import InsufficientFunds

    c, o = setup
    t = accepted(make_trade, c, o, [(True, Line(coins=1000))])
    ts.approve_trade(t, "sender", player)
    with mock.patch(
        "player_characters.trade_services.record_many", side_effect=InsufficientFunds("short")
    ):
        with pytest.raises(TradeError):
            ts.approve_trade(t, "receiver", other_player)
    t.refresh_from_db()
    assert not t.sender_approved and not t.receiver_approved
    assert t.status == "accepted"
    assert not LedgerEntry.objects.filter(kind="trade").exists()


def test_decline_cancel(setup, make_trade, player, other_player):
    c, o = setup
    t = make_trade(c, o)
    with pytest.raises(TradeError):
        ts.decline_trade(t, player)
    with pytest.raises(TradeError):
        ts.cancel_trade(t, other_player)
    ts.decline_trade(t, other_player)
    assert t.status == "declined"
    t2 = accepted(make_trade, c, o)
    ts.cancel_trade(t2, player)
    assert t2.status == "cancelled"
    t3 = accepted(make_trade, c, o)
    ts.decline_trade(t3, other_player)
    assert t3.status == "declined"


@pytest.mark.parametrize("status", ["completed", "declined", "cancelled"])
def test_final_states_reject(setup, make_trade, item, player, other_player, status):
    c, o = setup
    t = make_trade(c, o, lines=[(True, Line(coins=1))], status=status)
    for fn, args in (
        (ts.accept_trade, (other_player,)),
        (ts.decline_trade, (other_player,)),
        (ts.cancel_trade, (player,)),
        (ts.set_side, ("sender", [], player)),
        (ts.approve_trade, ("sender", player)),
    ):
        with pytest.raises(TradeError):
            fn(t, *args)
