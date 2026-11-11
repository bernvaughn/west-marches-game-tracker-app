from django.shortcuts import render
from django.views.decorators.http import require_POST

from ..permissions import club_admin_required, club_member_required


@club_member_required
def message_new(request, club_slug):
    return render(request, "accounts/stub.html", {"title": "Message admins"})


@club_admin_required
def message_inbox(request, club_slug):
    return render(request, "accounts/stub.html", {"title": "Inbox"})


@club_admin_required
@require_POST
def message_status(request, club_slug, pk):
    return render(request, "accounts/stub.html", {"title": "Message status"})
