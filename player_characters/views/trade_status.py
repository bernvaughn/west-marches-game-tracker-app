from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..models import Trade
from ..trade_services import (
    TradeError,
    accept_trade,
    can_view_trade,
    cancel_trade,
    decline_trade,
    side_of,
)


def _act(request, club_slug, pk, service, done):
    trade = club_get_object_or_404(request, Trade, pk=pk)
    if not can_view_trade(request.user, trade):
        raise Http404
    if side_of(trade, request.user) is None:
        raise PermissionDenied
    try:
        service(trade, request.user)
    except TradeError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, done)
    return redirect("trades:detail", club_slug, trade.pk)


@club_member_required
@require_POST
def accept(request, club_slug, pk):
    return _act(request, club_slug, pk, accept_trade, "Trade accepted.")


@club_member_required
@require_POST
def decline(request, club_slug, pk):
    return _act(request, club_slug, pk, decline_trade, "Trade declined.")


@club_member_required
@require_POST
def cancel(request, club_slug, pk):
    return _act(request, club_slug, pk, cancel_trade, "Trade cancelled.")
