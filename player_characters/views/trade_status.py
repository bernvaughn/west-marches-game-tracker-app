from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

import json

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


def _act(request, club_slug, pk, service, done=None, success_url="trades:detail", toast_type=None):
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
        if done:
            messages.success(request, done)
        # Emit toast via HX-Trigger for HTMX requests
        if request.headers.get("HX-Request") and toast_type:
            response = redirect(success_url, club_slug, trade.pk)
            response["HX-Trigger"] = json.dumps({"toast": {"message": done, "type": toast_type}})
            return response
        return redirect(success_url, club_slug, trade.pk)
    return redirect("trades:detail", club_slug, trade.pk)


@club_member_required
@require_POST
def accept(request, club_slug, pk):
    return _act(
        request,
        club_slug,
        pk,
        accept_trade,
        "Trade accepted. Choose what you give.",
        success_url="trades:edit_side",
        toast_type="success",
    )


@club_member_required
@require_POST
def decline(request, club_slug, pk):
    return _act(
        request,
        club_slug,
        pk,
        decline_trade,
        "Trade declined.",
        toast_type="warning",
    )


@club_member_required
@require_POST
def cancel(request, club_slug, pk):
    return _act(
        request,
        club_slug,
        pk,
        cancel_trade,
        "Trade cancelled.",
        toast_type="warning",
    )