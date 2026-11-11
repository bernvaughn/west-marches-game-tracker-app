from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from quests.models import Quest


@club_member_required
def index(request, club_slug):
    quests = Quest.objects.for_club(request.club).live_on(timezone.localdate())
    return render(request, "quests/index.html", {"quests": quests})


@club_member_required
def detail(request, club_slug, pk):
    quest = club_get_object_or_404(request, Quest, pk=pk)
    return render(request, "quests/_stub.html", {"title": quest.name})


@club_member_required
@require_POST
def turn_in(request, club_slug, pk):
    club_get_object_or_404(request, Quest, pk=pk)
    return redirect("quests:detail", club_slug=request.club.slug, pk=pk)
