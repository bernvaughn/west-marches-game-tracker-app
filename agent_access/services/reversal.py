"""Reverse a confirmed agent batch through the ledger service."""

from django.db import transaction
from django.utils import timezone

from ledger.models import LedgerEntry
from ledger.services import Line, record_many

from ..models import ProposedBatch


class BatchNotReversible(Exception):
    pass


def reverse_batch(batch, actor):
    """Write one reversal per award entry of `batch`. Return the new entries.

    Raises BatchNotReversible, or the ledger's InsufficientFunds/InsufficientItems.
    On any error nothing changes.
    """
    with transaction.atomic():
        batch = ProposedBatch.objects.select_for_update().get(pk=batch.pk)
        if batch.status != ProposedBatch.Status.CONFIRMED:
            raise BatchNotReversible("Only a confirmed batch can be reversed.")
        originals = (
            LedgerEntry.objects.filter(agent_batch=batch, kind=LedgerEntry.Kind.AWARD)
            .select_related("character", "character__club")
            .prefetch_related("lines__item")
            .order_by("id")
        )
        specs = [
            dict(
                character=e.character,
                kind=LedgerEntry.Kind.REVERSAL,
                lines=[
                    Line(item=line.item, quantity=-line.quantity, coins=-line.coins)
                    for line in e.lines.all()
                ],
                note=f"reversal of agent batch #{batch.pk}",
                actor=actor,
                via_agent=False,
                agent_batch=batch,
                reverses=e,
            )
            for e in originals
        ]
        entries = record_many(specs) if specs else []
        batch.status = ProposedBatch.Status.REVERSED
        batch.reversed_at = timezone.now()
        batch.reversed_by = actor
        batch.save(update_fields=["status", "reversed_at", "reversed_by"])
        return entries
