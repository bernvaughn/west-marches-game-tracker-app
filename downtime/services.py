"""Downtime point services."""

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from downtime.models import DowntimePointEntry
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


def spend(character, action, by, rng=None):
    """Spend points on an action and return the DowntimeResult.

    Contract (epic spec section 2): in one transaction, lock the character's point
    rows, check the action is live today and has entries, check the balance covers
    action.cost, pick an entry weighted by weight (``rng`` defaults to
    ``secrets.SystemRandom()``), write a ``spend`` entry, give coins and items through
    ``ledger.services.record`` and store a DowntimeResult. Raise InsufficientPoints
    or DowntimeError on refusal.
    """
    raise NotImplementedError
