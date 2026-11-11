from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404
from quests.models import Quest


@club_admin_required
def quest_list(request, club_slug):
    return render(request, "quests/_stub.html", {"title": "Manage quests"})


@club_admin_required
def quest_create(request, club_slug):
    return render(request, "quests/_stub.html", {"title": "New quest"})


@club_admin_required
def quest_edit(request, club_slug, pk):
    quest = club_get_object_or_404(request, Quest, pk=pk)
    return render(request, "quests/_stub.html", {"title": f"Edit {quest.name}"})


@club_admin_required
@require_POST
def quest_delete(request, club_slug, pk):
    club_get_object_or_404(request, Quest, pk=pk)
    return redirect("quests:manage", club_slug=request.club.slug)
