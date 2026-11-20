"""Ledger service: the only place that writes ledger entries."""

from collections import defaultdict
from dataclasses import dataclass

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from core.services import BaseService, ClubScopedService

from .models import LedgerEntry, LedgerLine


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


class LedgerService(BaseService, ClubScopedService):
    """
    Service for ledger operations.

    Combines BaseService for transaction handling and ClubScopedService
    for club-scoped validation and queries.
    """

    def validate(self, *args, **kwargs):
        """
        Validate inputs. This is called by the base class before operations.
        Individual methods perform their own validation.
        """
        pass

    def coin_balance(self, character):
        """Return total coin balance for a character."""
        total = LedgerLine.objects.filter(entry__character=character).aggregate(t=Sum("coins"))["t"]
        return total or 0

    def item_quantities(self, character):
        """Return {item_id: quantity} for items the character owns (non-zero only)."""
        rows = (
            LedgerLine.objects.filter(entry__character=character, item__isnull=False)
            .values("item_id")
            .annotate(total=Sum("quantity"))
        )
        return {r["item_id"]: r["total"] for r in rows if r["total"]}

    def held_coins(self, character):
        return 0

    def held_items(self, character):
        return {}

    def available_coins(self, character):
        return self.coin_balance(character)

    def available_items(self, character):
        return self.item_quantities(character)

    def _validate_spec(self, spec):
        """Validate a single record spec."""
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
                # Use club-scoping validation
                try:
                    self.ensure_same_club(character, line.item)
                except ValueError as e:
                    raise LedgerError(str(e)) from e

    def record_many(self, specs):
        """
        Write several entries atomically. Each spec is a dict of `record` keyword args.

        Negative amounts are summed per character across the whole batch and checked
        against availability; positives never fund negatives in the same batch.
        """
        specs = [dict(s) for s in specs]
        with self.atomic():
            for spec in specs:
                self._validate_spec(spec)

            spend_coins = defaultdict(int)
            spend_items = defaultdict(lambda: defaultdict(int))
            characters = {}
            for spec in specs:
                c = spec["character"]
                characters[c.pk] = c
                for line in spec["lines"]:
                    if line.coins < 0:
                        spend_coins[c.pk] += -line.coins
                    if line.item is not None and line.quantity < 0:
                        spend_items[c.pk][line.item] += -line.quantity

            for pk, needed in spend_coins.items():
                c = characters[pk]
                have = self.available_coins(c)
                if needed > have:
                    raise InsufficientFunds(f"{c} has {have} cp available but needs {needed} cp.")
            for pk, items in spend_items.items():
                c = characters[pk]
                avail = self.available_items(c)
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

    def record(
        self,
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
        source_message=None,
    ):
        return self.record_many(
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
                    source_message=source_message,
                )
            ]
        )[0]

    RECENT_KINDS = ("consumed", "adjustment", "award", "opened")

    def recent_changes(self, character, days=30, limit=20):
        """Consume and adjust entries (any actor) in the last `days`, newest first."""
        since = timezone.localdate() - timezone.timedelta(days=days)
        return list(
            LedgerEntry.objects.filter(
                character=character, kind__in=self.RECENT_KINDS, date__gte=since
            )
            .select_related("created_by")
            .prefetch_related(
                models.Prefetch(
                    "lines", queryset=LedgerLine.objects.select_related("item").order_by("id")
                )
            )
            .order_by("-date", "-id")[:limit]
        )


# Backward-compatible module-level functions
_service = LedgerService()


def coin_balance(character):
    return _service.coin_balance(character)


def item_quantities(character):
    return _service.item_quantities(character)


def held_coins(character):
    return _service.held_coins(character)


def held_items(character):
    return _service.held_items(character)


def available_coins(character):
    return _service.available_coins(character)


def available_items(character):
    return _service.available_items(character)


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
    source_message=None,
):
    return _service.record(
        character,
        kind,
        lines,
        note=note,
        date=date,
        actor=actor,
        via_agent=via_agent,
        shop=shop,
        agent_batch=agent_batch,
        reverses=reverses,
        source_message=source_message,
    )


def record_many(specs):
    return _service.record_many(specs)


def recent_changes(character, days=30, limit=20):
    return _service.recent_changes(character, days, limit)
