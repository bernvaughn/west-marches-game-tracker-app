"""Ledger service: the only place that writes ledger entries."""

from collections import defaultdict
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from player_characters.models import Trade, TradeLine

from .models import LedgerEntry, LedgerLine

OPEN_TRADE_STATUSES = (Trade.Status.REQUESTED, Trade.Status.ACCEPTED)


class LedgerError(Exception):
    """Base class for ledger service errors."""


class InsufficientFunds(LedgerError):
    pass


class InsufficientItems(LedgerError):
    pass


@dataclass(frozen=True)
class Line:
    item: object = None
    quantity: int = 0
    coins: int = 0


def coin_balance(character):
    total = LedgerLine.objects.filter(entry__character=character).aggregate(t=Sum("coins"))["t"]
    return total or 0


def item_quantities(character):
    """Return {item_id: quantity} for items the character owns (non-zero only)."""
    rows = (
        LedgerLine.objects.filter(entry__character=character, item__isnull=False)
        .values("item_id")
        .annotate(total=Sum("quantity"))
    )
    return {r["item_id"]: r["total"] for r in rows if r["total"]}


def _hold_lines(character, exclude_trade=None):
    """Give-side trade lines of open trades for this character."""
    qs = TradeLine.objects.filter(
        Q(trade__sender=character, from_sender=True)
        | Q(trade__receiver=character, from_sender=False),
        trade__status__in=OPEN_TRADE_STATUSES,
    )
    if exclude_trade is not None:
        qs = qs.exclude(trade=exclude_trade)
    return qs


def held_coins(character, exclude_trade=None):
    return _hold_lines(character, exclude_trade).aggregate(t=Sum("coins"))["t"] or 0


def held_items(character, exclude_trade=None):
    rows = (
        _hold_lines(character, exclude_trade)
        .filter(item__isnull=False)
        .values("item_id")
        .annotate(total=Sum("quantity"))
    )
    return {r["item_id"]: r["total"] for r in rows if r["total"]}


def available_coins(character, exclude_trade=None):
    return coin_balance(character) - held_coins(character, exclude_trade)


def available_items(character, exclude_trade=None):
    owned = item_quantities(character)
    held = held_items(character, exclude_trade)
    result = {i: q - held.get(i, 0) for i, q in owned.items()}
    return {i: q for i, q in result.items() if q}


def record(
    character,
    kind,
    lines,
    note="",
    date=None,
    actor=None,
    via_agent=False,
    shop=None,
    agent_batch=None,
    reverses=None,
    exclude_trade=None,
    source_message=None,
):
    return record_many(
        [
            dict(
                character=character,
                kind=kind,
                lines=lines,
                note=note,
                date=date,
                actor=actor,
                via_agent=via_agent,
                shop=shop,
                agent_batch=agent_batch,
                reverses=reverses,
                exclude_trade=exclude_trade,
                source_message=source_message,
            )
        ]
    )[0]


def _validate(spec):
    character = spec["character"]
    if spec["kind"] not in LedgerEntry.Kind.values:
        raise LedgerError(f"Unknown entry kind: {spec['kind']!r}")
    lines = spec.get("lines") or []
    if not lines:
        raise LedgerError("An entry needs at least one line.")
    for line in lines:
        if line.item is None:
            if not line.coins:
                raise LedgerError("A line needs an item or coins.")
            if line.quantity:
                raise LedgerError("A coin line cannot have a quantity.")
        else:
            if not line.quantity:
                raise LedgerError(f"Line for {line.item} needs a non-zero quantity.")
            if line.item.club_id != character.club_id:
                raise LedgerError(f"{line.item} belongs to a different club.")


def record_many(specs):
    """Write several entries atomically. Each spec is a dict of `record` keyword args.

    Negative amounts are summed per character across the whole batch and checked
    against availability; positives never fund negatives in the same batch. If
    specs for one character give different `exclude_trade` values, the first
    non-None one is used.
    """
    specs = [dict(s) for s in specs]
    with transaction.atomic():
        for spec in specs:
            _validate(spec)

        spend_coins = defaultdict(int)
        spend_items = defaultdict(lambda: defaultdict(int))
        characters = {}
        exclude = {}
        for spec in specs:
            c = spec["character"]
            characters[c.pk] = c
            if exclude.get(c.pk) is None:
                exclude[c.pk] = spec.get("exclude_trade")
            for line in spec["lines"]:
                if line.coins < 0:
                    spend_coins[c.pk] += -line.coins
                if line.item is not None and line.quantity < 0:
                    spend_items[c.pk][line.item] += -line.quantity

        for pk, needed in spend_coins.items():
            c = characters[pk]
            have = available_coins(c, exclude[pk])
            if needed > have:
                raise InsufficientFunds(f"{c} has {have} cp available but needs {needed} cp.")
        for pk, items in spend_items.items():
            c = characters[pk]
            avail = available_items(c, exclude[pk])
            for item, needed in items.items():
                have = avail.get(item.pk, 0)
                if needed > have:
                    raise InsufficientItems(
                        f"{c} has {have} x {item} available but needs {needed}."
                    )

        entries = []
        for spec in specs:
            c = spec["character"]
            entry = LedgerEntry.objects.create(
                club=c.club,
                character=c,
                date=spec.get("date") or timezone.localdate(),
                note=spec.get("note", ""),
                kind=spec["kind"],
                created_by=spec.get("actor"),
                via_agent=spec.get("via_agent", False),
                shop=spec.get("shop"),
                agent_batch=spec.get("agent_batch"),
                reverses=spec.get("reverses"),
                source_message=spec.get("source_message"),
            )
            for line in spec["lines"]:
                LedgerLine.objects.create(
                    entry=entry, item=line.item, quantity=line.quantity, coins=line.coins
                )
            entries.append(entry)
        return entries
