"""Approval provider for the navbar indicator (U26)."""

from django.urls import reverse

from .models import Message
from .permissions import is_club_admin


def open_messages(request):
    club = getattr(request, "club", None)
    if club is None or not is_club_admin(request.user, club):
        return None
    count = Message.objects.for_club(club).filter(status=Message.Status.OPEN).count()
    return ("Messages", count, reverse("accounts:message_inbox", args=[club.slug]))
