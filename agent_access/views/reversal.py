import logging

from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from accounts.permissions import game_master_required
from accounts.scoping import club_get_object_or_404
from ledger.services import LedgerError

from ..models import ProposedBatch
from ..services.reversal import BatchNotReversible, reverse_batch

batch_logger = logging.getLogger("security.batch")


@game_master_required
@require_POST
def batch_reverse(request, club_slug, pk):
    batch = club_get_object_or_404(request, ProposedBatch, pk=pk)
    try:
        entries = reverse_batch(batch, request.user)
    except (BatchNotReversible, LedgerError) as exc:
        messages.error(request, str(exc))
        batch_logger.warning(
            "Batch reversal failed",
            extra={
                "batch_id": batch.pk,
                "club_id": request.club.id,
                "actor_id": request.user.id,
                "error": str(exc),
            },
        )
    else:
        messages.success(
            request, f"Batch #{batch.pk} reversed: {len(entries)} ledger entries written."
        )
        batch_logger.info(
            "Batch reversed",
            extra={
                "batch_id": batch.pk,
                "club_id": request.club.id,
                "actor_id": request.user.id,
                "entries_count": len(entries),
            },
        )
    return redirect("agent_access:batch_detail", club_slug=club_slug, pk=batch.pk)