"""HTMX poll fragment for trade status updates."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from accounts.permissions import club_member_required
from accounts.scoping import club_queryset

from ..models import Trade
from ..trade_services import OPEN, side_of
from ..trade_status_line import trade_status_line


@club_member_required
@require_GET
def poll(request, club_slug):
    """Return JSON with trade status updates for all open trades."""
    trades = club_queryset(request, Trade).filter(
        status__in=OPEN
    ).select_related("sender__owner__user", "receiver__owner__user")

    user = request.user
    result = []
    for trade in trades:
        viewer_side = side_of(trade, user)
        if viewer_side is None and not (
            user.is_superuser
            or getattr(request, "membership", None)
            and (request.membership.is_game_master or request.membership.is_club_admin)
        ):
            continue

        result.append(
            {
                "pk": trade.pk,
                "status": trade.status,
                "status_display": trade.get_status_display(),
                "status_line": trade_status_line(trade, viewer_side),
                "sender_approved": trade.sender_approved,
                "receiver_approved": trade.receiver_approved,
                "viewer_side": viewer_side,
            }
        )

    return JsonResponse({"count": len(result), "trades": result})