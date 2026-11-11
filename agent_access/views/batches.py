from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import game_master_required
from accounts.scoping import club_get_object_or_404

from ..models import ProposedBatch


@game_master_required
def batch_list(request, club_slug):
    return render(request, "agent_access/stub.html", {"title": "Batches"})


@game_master_required
def batch_detail(request, club_slug, pk):
    batch = club_get_object_or_404(request, ProposedBatch, pk=pk)
    return render(request, "agent_access/stub.html", {"title": f"Batch {batch.pk}"})


@game_master_required
@require_POST
def batch_confirm(request, club_slug, pk):
    club_get_object_or_404(request, ProposedBatch, pk=pk)
    return redirect("agent_access:batches", club_slug=club_slug)


@game_master_required
@require_POST
def batch_discard(request, club_slug, pk):
    club_get_object_or_404(request, ProposedBatch, pk=pk)
    return redirect("agent_access:batches", club_slug=club_slug)
