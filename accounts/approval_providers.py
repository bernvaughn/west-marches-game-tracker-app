"""Approval provider for the navbar indicator (U26)."""

from django.db.models import Q
from django.urls import reverse

from player_characters.models import Trade

from .models import Message
from .permissions import is_club_admin


def open_messages(request):
    club = getattr(request, "club", None)
    if club is None or not is_club_admin(request.user, club):
        return None
    count = Message.objects.for_club(club).filter(status=Message.Status.OPEN).count()
    return ("Messages", count, reverse("accounts:message_inbox", args=[club.slug]))


def open_trades_needing_action(request):
    """Count trades where the current user's character must approve/accept/decline."""
    club = getattr(request, "club", None)
    user = getattr(request, "user", None)
    if club is None or user is None or not user.is_authenticated:
        return None

    # Get user's characters in this club
    user_chars = user.memberships.filter(club=club).values_list("characters__pk", flat=True)
    if not user_chars:
        return None

    # Trades where user is sender or receiver AND trade is open (requested/accepted)
    # AND the user's character needs to take action:
    # - If REQUESTED and user is receiver: needs to accept/decline
    # - If ACCEPTED and user is sender/receiver and hasn't approved: needs to approve
    trades = Trade.objects.for_club(club).filter(
        Q(sender_id__in=user_chars) | Q(receiver_id__in=user_chars),
        status__in=[Trade.Status.REQUESTED, Trade.Status.ACCEPTED],
    )

    count = 0
    for trade in trades.select_related("sender", "receiver"):
        if trade.status == Trade.Status.REQUESTED and trade.receiver_id in user_chars:
            count += 1
        elif trade.status == Trade.Status.ACCEPTED:
            if trade.sender_id in user_chars and not trade.sender_approved:
                count += 1
            elif trade.receiver_id in user_chars and not trade.receiver_approved:
                count += 1

    if count == 0:
        return None
    return ("Trades", count, reverse("trades:index", args=[club.slug]))