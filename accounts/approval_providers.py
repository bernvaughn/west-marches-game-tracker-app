"""Approval providers for the navbar indicator (U26, Contract)."""

from django.db.models import Q
from django.urls import reverse

from .models import Message
from .permissions import is_club_admin
from accounts.scoping import club_queryset
from player_characters.models import Trade


def open_messages(request):
    club = getattr(request, "club", None)
    if club is None or not is_club_admin(request.user, club):
        return None
    count = Message.objects.for_club(club).filter(status=Message.Status.OPEN).count()
    return ("Messages", count, reverse("accounts:message_inbox", args=[club.slug]))


def pending_trades(request):
    club = getattr(request, "club", None)
    user = getattr(request, "user", None)
    if club is None or user is None or not user.is_authenticated:
        return None
    # Count trades where the user is sender or receiver and trade is in open state
    membership = getattr(request, "membership", None)
    if not membership:
        return None
    open_statuses = [Trade.Status.REQUESTED, Trade.Status.ACCEPTED]
    count = club_queryset(request, Trade).filter(
        Q(sender__owner=membership) | Q(receiver__owner=membership),
        status__in=open_statuses,
    ).count()
    if count == 0:
        return None
    return ("Trades", count, reverse("trades:index", args=[club.slug]))