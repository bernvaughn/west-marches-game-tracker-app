from django.http import HttpResponse
from django.shortcuts import render

from accounts.permissions import club_member_required


@club_member_required
def index(request, club_slug):
    return render(request, "player_characters/trades/index.html")


@club_member_required
def propose(request, club_slug):
    # Stub: filled by the "Propose a trade and list trades" story.
    return HttpResponse(status=501)
