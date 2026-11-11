"""Trade service: every trade rule and state change lives here."""

from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from accounts.permissions import is_club_admin, is_game_master
from ledger.coins import format_coins
from ledger.services import (
    LedgerError,
    Line,
    available_coins,
    available_items,
    record_many,
)

from .models import Trade, TradeLine

OPEN = (Trade.Status.REQUESTED, Trade.Status.ACCEPTED)


class TradeError(Exception):
    """A trade rule failed. The message is safe to show to users."""


def _owner_user_id(character):
    return character.owner.user_id


def side_of(trade, user):
    if user is None or not user.is_authenticated:
        return None
    if _owner_user_id(trade.sender) == user.pk:
        return "sender"
    if _owner_user_id(trade.receiver) == user.pk:
        return "receiver"
    return None


def can_view_trade(user, trade):
    if user is None or not user.is_authenticated:
        return False
    return (
        side_of(trade, user) is not None
        or is_game_master(user, trade.club)
        or is_club_admin(user, trade.club)
    )


def side_lines(trade, side):
    return list(trade.lines.filter(from_sender=(side == "sender")).select_related("item"))


def _normalise(lines, club):
    items = {}
    qty = defaultdict(int)
    coins = 0
    for line in lines:
        if line.item is not None and line.coins:
            raise TradeError("A line cannot hold both an item and coins.")
        if line.quantity < 0 or line.coins < 0:
            raise TradeError("Amounts cannot be negative.")
        if line.item is not None:
            if line.item.club_id != club.pk:
                raise TradeError(f"{line.item} belongs to a different club.")
            items[line.item.pk] = line.item
            qty[line.item.pk] += line.quantity
        else:
            coins += line.coins
    out = [Line(item=items[pk], quantity=q) for pk, q in sorted(qty.items()) if q]
    if coins:
        out.append(Line(coins=coins))
    return tuple(out)


def _check_available(character, lines, exclude_trade):
    avail_items = available_items(character, exclude_trade)
    for line in lines:
        if line.item is not None:
            have = avail_items.get(line.item.pk, 0)
            if line.quantity > have:
                raise TradeError(f"{character.name} has only {have} x {line.item.name} available.")
        elif line.coins > available_coins(character, exclude_trade):
            have = available_coins(character, exclude_trade)
            raise TradeError(f"{character.name} has only {format_coins(have)} available.")


def _write_lines(trade, from_sender, lines):
    trade.lines.filter(from_sender=from_sender).delete()
    TradeLine.objects.bulk_create(
        [
            TradeLine(
                trade=trade,
                from_sender=from_sender,
                item=ln.item,
                quantity=ln.quantity,
                coins=ln.coins,
            )
            for ln in lines
        ]
    )


def _character(trade, side):
    return trade.sender if side == "sender" else trade.receiver


def _require_owner(trade, side, actor):
    character = _character(trade, side)
    if actor is None or _owner_user_id(character) != actor.pk:
        raise TradeError(f"Only the owner of {character.name} can do that.")


def _lock(trade):
    trade.refresh_from_db()


def propose_trade(sender, receiver, lines, note, actor):
    with transaction.atomic():
        if actor is None or _owner_user_id(sender) != actor.pk:
            raise TradeError(f"Only the owner of {sender.name} can do that.")
        if sender.club_id != receiver.club_id:
            raise TradeError("Both characters must be in the same club.")
        if _owner_user_id(receiver) == _owner_user_id(sender):
            raise TradeError("You cannot trade with your own character.")
        lines = _normalise(lines, sender.club)
        note = (note or "").strip()
        if not lines and not note:
            raise TradeError("Offer something or write a note.")
        _check_available(sender, lines, None)
        trade = Trade.objects.create(
            club=sender.club,
            sender=sender,
            receiver=receiver,
            note=note,
            status=Trade.Status.REQUESTED,
        )
        _write_lines(trade, True, lines)
        return trade


def accept_trade(trade, actor):
    with transaction.atomic():
        _lock(trade)
        _require_owner(trade, "receiver", actor)
        if trade.status != Trade.Status.REQUESTED:
            raise TradeError("This trade is not waiting for a reply.")
        if (
            Trade.objects.filter(sender=trade.sender, status=Trade.Status.ACCEPTED)
            .exclude(pk=trade.pk)
            .exists()
        ):
            raise TradeError(f"{trade.sender.name} already has another accepted trade.")
        trade.status = Trade.Status.ACCEPTED
        trade.save(update_fields=["status", "updated"])
    return trade


def set_side(trade, side, lines, actor):
    with transaction.atomic():
        _lock(trade)
        _require_owner(trade, side, actor)
        if trade.status != Trade.Status.ACCEPTED:
            raise TradeError("Sides can change only while the trade is accepted.")
        if getattr(trade, f"{side}_approved"):
            raise TradeError("You approved this trade. Nothing can change now.")
        character = _character(trade, side)
        new = _normalise(lines, trade.club)
        _check_available(character, new, trade)
        current = _normalise(
            [
                Line(item=ln.item, quantity=ln.quantity, coins=ln.coins)
                for ln in side_lines(trade, side)
            ],
            trade.club,
        )
        if new != current:
            _write_lines(trade, side == "sender", new)
            trade.sender_approved = False
            trade.receiver_approved = False
            trade.save(update_fields=["sender_approved", "receiver_approved", "updated"])
    return trade


def approve_trade(trade, side, actor):
    with transaction.atomic():
        _lock(trade)
        _require_owner(trade, side, actor)
        if trade.status != Trade.Status.ACCEPTED:
            raise TradeError("Only an accepted trade can be approved.")
        if getattr(trade, f"{side}_approved"):
            raise TradeError("You already approved this trade.")
        if not trade.lines.exists():
            raise TradeError("Add something to the trade before approving.")
        setattr(trade, f"{side}_approved", True)
        trade.save(update_fields=[f"{side}_approved", "updated"])
    if trade.sender_approved and trade.receiver_approved:
        complete_trade(trade, actor)
    return trade


def _specs(trade, actor):
    specs = []
    for from_sender, mine, other in (
        (True, trade.sender, trade.receiver),
        (False, trade.receiver, trade.sender),
    ):
        lines = []
        for ln in trade.lines.select_related("item"):
            sign = -1 if ln.from_sender == from_sender else 1
            if ln.item is not None:
                lines.append(Line(item=ln.item, quantity=sign * ln.quantity))
            else:
                lines.append(Line(coins=sign * ln.coins))
        specs.append(
            dict(
                character=mine,
                kind="trade",
                lines=lines,
                note=f"Trade with {other.name}",
                actor=actor,
                exclude_trade=trade,
                date=timezone.localdate(),
            )
        )
    return specs


def complete_trade(trade, actor):
    """Complete an accepted trade with both approvals. Not atomic on its own failure path:
    a ledger failure clears both approvals in a separate transaction, then raises."""
    error = None
    with transaction.atomic():
        _lock(trade)
        if trade.status != Trade.Status.ACCEPTED:
            raise TradeError("Only an accepted trade can complete.")
        if not (trade.sender_approved and trade.receiver_approved):
            raise TradeError("Both players must approve first.")
        if actor is None or side_of(trade, actor) is None:
            raise TradeError("Only a player in the trade can complete it.")
        try:
            with transaction.atomic():
                record_many(_specs(trade, actor))
        except LedgerError as err:
            error = str(err)
            trade.sender_approved = False
            trade.receiver_approved = False
            trade.save(update_fields=["sender_approved", "receiver_approved", "updated"])
        else:
            trade.status = Trade.Status.COMPLETED
            trade.save(update_fields=["status", "updated"])
    if error is not None:
        raise TradeError(f"The trade could not complete: {error} Approvals were cleared.")
    return trade


def _close(trade, side, actor, status):
    with transaction.atomic():
        _lock(trade)
        _require_owner(trade, side, actor)
        if trade.status not in OPEN:
            raise TradeError("This trade is already closed.")
        trade.status = status
        trade.save(update_fields=["status", "updated"])
    return trade


def decline_trade(trade, actor):
    return _close(trade, "receiver", actor, Trade.Status.DECLINED)


def cancel_trade(trade, actor):
    return _close(trade, "sender", actor, Trade.Status.CANCELLED)
