"""Downtime point services."""

import secrets

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from downtime.models import DowntimePointEntry, DowntimeResult
from ledger.services import Line
from ledger.services import record as ledger_record
from player_characters.models import Character


class DowntimeError(Exception):
    pass


class InsufficientPoints(DowntimeError):
    pass


def balance(character):
    return DowntimePointEntry.objects.filter(character=character).aggregate(
        total=Coalesce(Sum("delta"), 0)
    )["total"]


def award(characters, delta, note="", date=None, by=None, kind="award", source="", *, club=None):
    """Write one point entry per character; refuse a negative resulting balance."""
    if isinstance(characters, Character):
        characters = [characters]
    # One entry and one balance check per character, even if listed twice.
    unique = {}
    for c in characters:
        unique.setdefault(c.pk, c)
    characters = list(unique.values())
    if not characters:
        raise DowntimeError("No characters given.")
    if not delta:
        raise DowntimeError("Delta cannot be zero.")
    if kind not in DowntimePointEntry.Kind.values:
        raise DowntimeError(f"Unknown kind: {kind}")
    club_ids = {c.club_id for c in characters}
    if len(club_ids) > 1:
        raise DowntimeError("Characters belong to more than one club.")
    if club is not None and club_ids != {club.pk}:
        raise DowntimeError("Character is not in this club.")
    date = date or timezone.localdate()
    pks = {c.pk for c in characters}
    with transaction.atomic():
        list(Character.objects.select_for_update().filter(pk__in=pks).order_by("pk"))
        for c in characters:
            if balance(c) + delta < 0:
                raise InsufficientPoints(f"{c} does not have enough downtime points.")
        return [
            DowntimePointEntry.objects.create(
                character=c,
                delta=delta,
                note=note,
                date=date,
                kind=kind,
                created_by=by,
                source=source,
            )
            for c in characters
        ]


def chances(entries):
    """[(entry, percent)] with percent = weight / total weight * 100 (unrounded)."""
    entries = list(entries)
    total = sum(e.weight for e in entries)
    if not total:
        return [(e, 0) for e in entries]
    return [(e, e.weight * 100 / total) for e in entries]


def spend(character, action, by, rng=None, *, today=None):
    """Spend points on an action and return the DowntimeResult.

    In one transaction: lock the character, check the action is live and has entries,
    check the balance covers action.cost, pick an entry weighted by weight, write a
    ``spend`` entry, give coins and items through ``ledger.services.record`` (kind
    "award") and store a DowntimeResult. Raise InsufficientPoints or DowntimeError on
    refusal.
    """
    if action.club_id != character.club_id:
        raise DowntimeError("That action is not available in this club.")
    today = today or timezone.localdate()
    with transaction.atomic():
        list(Character.objects.select_for_update().filter(pk=character.pk))
        if not action.is_live_on(today):
            raise DowntimeError(f"{action.name} is not available today.")
        entries = list(action.entries.prefetch_related("items__item"))
        if not entries:
            raise DowntimeError(f"{action.name} has no rewards yet.")
        if balance(character) < action.cost:
            raise InsufficientPoints(f"{character} does not have enough downtime points.")
        rng = rng or secrets.SystemRandom()
        entry = rng.choices(entries, weights=[e.weight for e in entries], k=1)[0]
        DowntimePointEntry.objects.create(
            character=character,
            delta=-action.cost,
            note=f"{action.name}: {entry.label}",
            date=today,
            kind=DowntimePointEntry.Kind.SPEND,
            created_by=by,
            source=f"downtime_action:{action.pk}",
        )
        lines = []
        if entry.coins:
            lines.append(Line(coins=entry.coins))
        lines.extend(Line(ei.item, ei.quantity) for ei in entry.items.all())
        ledger_entry = None
        if lines:
            ledger_entry = ledger_record(
                character,
                "award",
                lines,
                note=f"Downtime: {action.name} - {entry.label}",
                actor=by,
            )
        return DowntimeResult.objects.create(
            character=character, action=action, entry=entry, ledger_entry=ledger_entry
        )
