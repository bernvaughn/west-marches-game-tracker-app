from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import game_master_required
from accounts.scoping import club_get_object_or_404

from ..models import AgentConnection


@game_master_required
def connection_list(request, club_slug):
    return render(request, "agent_access/stub.html", {"title": "Connections"})


@game_master_required
@require_POST
def connection_revoke(request, club_slug, pk):
    club_get_object_or_404(request, AgentConnection, pk=pk)
    return redirect("agent_access:connections", club_slug=club_slug)
