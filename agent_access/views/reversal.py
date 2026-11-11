from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from accounts.permissions import game_master_required
from accounts.scoping import club_get_object_or_404
from ledger.services import LedgerError

from ..models import ProposedBatch
from ..services.reversal import BatchNotReversible, reverse_batch


@game_master_required
@require_POST
def batch_reverse(request, club_slug, pk):
    batch = club_get_object_or_404(request, ProposedBatch, pk=pk)
    try:
        entries = reverse_batch(batch, request.user)
    except (BatchNotReversible, LedgerError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, f"Batch #{batch.pk} reversed: {len(entries)} ledger entries written."
        )
    return redirect("agent_access:batch_detail", club_slug=club_slug, pk=batch.pk)
