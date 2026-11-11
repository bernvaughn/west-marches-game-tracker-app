from django.shortcuts import render

from accounts.permissions import club_member_required


@club_member_required
def index(request, club_slug):
    return render(request, "agent_access/index.html")
