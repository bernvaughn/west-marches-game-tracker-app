"""Trade poll fragment endpoint (Contract): returns trade status for navbar polling."""

from django.http import JsonResponse
from django.urls import reverse

from accounts.permissions import club_member_required
from accounts.scoping import club_queryset

from ..models import Trade
from ..selection import selected_character
from ..trade_services import OPEN


@club_member_required
def trade_poll(request, club_slug):
    """Return JSON with open trade count and status for the selected character."""
    character = selected_character(request)
    if not character:
        return JsonResponse({"count": 0, "trades": []})
    
    trades = club_queryset(request, Trade).filter(
        status__in=OPEN
    ).filter(
        sender=character
    ) | club_queryset(request, Trade).filter(
        status__in=OPEN
    ).filter(
        receiver=character
    )
    
    trade_data = []
    for t in trades.select_related("sender__owner__user", "receiver__owner__user"):
        if t.sender == character:
            other = t.receiver
            side = "sender"
        else:
            other = t.sender
            side = "receiver"
        
        trade_data.append({
            "id": t.pk,
            "status": t.status,
            "other_character": other.name,
            "other_player": other.owner.user.display_name,
            "side": side,
            "url": reverse("trades:detail", args=[request.club.slug, t.pk]),
            "updated": t.updated.isoformat(),
        })
    
    return JsonResponse({
        "count": len(trade_data),
        "trades": trade_data,
    })