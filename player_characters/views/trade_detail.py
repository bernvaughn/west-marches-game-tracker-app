from django.http import Http404
from django.shortcuts import get_object_or_404, render

from accounts.permissions import club_member_required
from accounts.scoping import club_queryset

from ..models import Trade
from ..trade_services import OPEN, can_view_trade, side_lines, side_of
from ..trade_status_line import trade_status_line


@club_member_required
def detail(request, club_slug, pk):
    trade = get_object_or_404(
        club_queryset(request, Trade).select_related(
            "sender__owner__user", "receiver__owner__user"
        ),
        pk=pk,
    )
    if not can_view_trade(request.user, trade):
        raise Http404
    side = side_of(trade, request.user)
    return render(
        request,
        "player_characters/trades/detail.html",
        {
            "trade": trade,
            "side": side,
            "status_line": trade_status_line(trade, side),
            "can_act": side is not None and trade.status in OPEN,
            "sender_lines": side_lines(trade, "sender"),
            "receiver_lines": side_lines(trade, "receiver"),
        },
    )
