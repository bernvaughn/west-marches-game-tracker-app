"""Ownership counts (U74): how many characters hold each item, and how many in total."""

from collections import defaultdict
from dataclasses import dataclass

from django.db.models import Sum

from ledger.models import LedgerLine


@dataclass(frozen=True)
class Ownership:
    characters: int
    held: int


def ownership_counts(club):
    """{item_id: Ownership} for items some character owns. Retired items are included.

    One query. Items nobody owns are absent; callers treat them as (0, 0).
    """
    rows = (
        LedgerLine.objects.filter(entry__character__club=club, item__isnull=False)
        .values("item_id", "entry__character_id")
        .annotate(q=Sum("quantity"))
        .filter(q__gt=0)
    )
    characters, held = defaultdict(int), defaultdict(int)
    for row in rows:
        characters[row["item_id"]] += 1
        held[row["item_id"]] += row["q"]
    return {i: Ownership(characters[i], held[i]) for i in characters}
