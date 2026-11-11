from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from accounts.permissions import game_master_required
from accounts.scoping import club_get_object_or_404

from ..models import ProposedBatch


@game_master_required
@require_POST
def batch_reverse(request, club_slug, pk):
    club_get_object_or_404(request, ProposedBatch, pk=pk)
    return redirect("agent_access:batches", club_slug=club_slug)
