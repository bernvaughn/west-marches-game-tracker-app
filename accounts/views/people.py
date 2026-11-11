from django.shortcuts import render

from ..permissions import club_admin_required, club_member_required


@club_member_required
def member_list(request, club_slug):
    return render(request, "accounts/index.html")


@club_admin_required
def whitelist(request, club_slug):
    return render(request, "accounts/stub.html", {"title": "Whitelist"})
