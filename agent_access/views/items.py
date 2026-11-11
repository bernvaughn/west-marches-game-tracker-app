from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404

from ..models import ProposedItem


@admin_or_gm_required
def proposed_item_list(request, club_slug):
    return render(request, "agent_access/stub.html", {"title": "Proposed items"})


@admin_or_gm_required
def proposed_item_detail(request, club_slug, pk):
    item = club_get_object_or_404(request, ProposedItem, pk=pk)
    return render(request, "agent_access/stub.html", {"title": item.name})


@admin_or_gm_required
@require_POST
def proposed_item_approve(request, club_slug, pk):
    club_get_object_or_404(request, ProposedItem, pk=pk)
    return redirect("agent_access:proposed_items", club_slug=club_slug)


@admin_or_gm_required
@require_POST
def proposed_item_reject(request, club_slug, pk):
    club_get_object_or_404(request, ProposedItem, pk=pk)
    return redirect("agent_access:proposed_items", club_slug=club_slug)
