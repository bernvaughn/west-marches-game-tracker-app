"""Confirm a proposed batch into the ledger."""

from django.db import transaction
from django.utils import timezone

from ledger import services as ledger
from ledger.services import LedgerError

from ..models import ProposedBatch, ProposedItem

AGENT_NOTE = "recorded through an agent"


class ConfirmError(Exception):
    def __init__(self, messages):
        self.messages = list(messages)
        super().__init__("; ".join(self.messages))


def ledger_note(note):
    note = (note or "").strip()
    return f"{note} — {AGENT_NOTE}" if note else AGENT_NOTE


def _resolve_item(line, n, problems):
    if line.item_id:
        if line.item.retired:
            problems.append(f"Line {n}: item {line.item} is retired.")
            return None
        return line.item
    proposed = line.proposed_item
    if proposed is None:
        return None
    if proposed.status == ProposedItem.Status.PENDING:
        problems.append(f"Line {n}: proposed item {proposed} is not approved yet.")
    elif proposed.status == ProposedItem.Status.REJECTED:
        problems.append(f"Line {n}: proposed item {proposed} was rejected.")
    elif proposed.approved_item is None:
        problems.append(f"Line {n}: proposed item {proposed} has no approved catalogue item.")
    elif proposed.approved_item.retired:
        problems.append(f"Line {n}: item {proposed.approved_item} is retired.")
    else:
        return proposed.approved_item
    return None


def confirm_batch(*, club, batch_id, actor):
    with transaction.atomic():
        batch = ProposedBatch.objects.for_club(club).get(pk=batch_id)
        if batch.status != ProposedBatch.Status.PENDING:
            raise ConfirmError([f"Batch #{batch.pk} is already {batch.status}."])
        lines = list(
            batch.lines.select_related(
                "character", "item", "proposed_item__approved_item"
            ).order_by("pk")
        )
        if not lines:
            raise ConfirmError(["An empty batch cannot be confirmed."])
        problems, specs = [], []
        for n, line in enumerate(lines, start=1):
            if line.item_id or line.proposed_item_id:
                item = _resolve_item(line, n, problems)
                amounts = [ledger.Line(item=item, quantity=line.quantity)]
            else:
                amounts = [ledger.Line(coins=line.coins)]
            specs.append(
                dict(
                    character=line.character,
                    kind="award",
                    lines=amounts,
                    note=ledger_note(line.note),
                    date=line.date or batch.date,
                    actor=actor,
                    via_agent=True,
                    agent_batch=batch,
                )
            )
        if problems:
            raise ConfirmError(problems)
        try:
            entries = ledger.record_many(specs)
        except LedgerError as exc:
            raise ConfirmError([str(exc)]) from exc
        batch.status = ProposedBatch.Status.CONFIRMED
        batch.confirmed_at = timezone.now()
        batch.confirmed_by = actor
        batch.save(update_fields=["status", "confirmed_at", "confirmed_by"])
        return entries
