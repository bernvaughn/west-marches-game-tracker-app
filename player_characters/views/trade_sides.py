from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.services import coin_balance, held_coins, held_items, item_quantities

from ..inventory import CoinSummary, InventoryRow
from ..models import Trade
from ..trade_forms import TradeSideForm
from ..trade_services import (
    TradeError,
    approve_trade,
    can_view_trade,
    set_side,
    side_lines,
    side_of,
)


def _get_trade(request, pk):
    trade = club_get_object_or_404(request, Trade, pk=pk)
    if not can_view_trade(request.user, trade):
        raise Http404
    side = side_of(trade, request.user)
    if side is None:
        raise PermissionDenied
    return trade, side


def _initial(trade, side):
    initial = {}
    coins = 0
    for line in side_lines(trade, side):
        if line.item_id:
            initial[f"item_{line.item_id}"] = line.quantity
        else:
            coins += line.coins
    initial["coins"] = coins
    return initial


def _offer_rows(character, trade, form):
    """Owned items with holds from other trades only; this trade's own holds are free."""
    owned = {i: q for i, q in item_quantities(character).items() if q > 0}
    held = held_items(character, trade)
    items = Item.objects.filter(pk__in=owned).order_by("name", "pk")
    rows = [InventoryRow(item=i, owned=owned[i.pk], held=held.get(i.pk, 0)) for i in items]
    return [
        (r, form[f"item_{r.item.pk}"] if f"item_{r.item.pk}" in form.fields else None) for r in rows
    ]


@club_member_required
@require_http_methods(["GET", "POST"])
def edit_side(request, club_slug, pk):
    trade, side = _get_trade(request, pk)
    detail = redirect("trades:detail", club_slug=club_slug, pk=trade.pk)
    character = trade.sender if side == "sender" else trade.receiver
    if request.method == "GET":
        if trade.status != Trade.Status.ACCEPTED:
            messages.error(request, "Sides can change only while the trade is accepted.")
            return detail
        if getattr(trade, f"{side}_approved"):
            messages.error(request, "You approved this trade. Nothing can change now.")
            return detail
        form = TradeSideForm(character, exclude_trade=trade, initial=_initial(trade, side))
    else:
        form = TradeSideForm(character, exclude_trade=trade, data=request.POST)
        if form.is_valid():
            try:
                set_side(trade, side, form.lines(), request.user)
            except TradeError as err:
                messages.error(request, str(err))
            else:
                messages.success(request, "Your side is saved.")
            return detail
    other = trade.receiver if side == "sender" else trade.sender
    return render(
        request,
        "player_characters/trades/edit_side.html",
        {
            "trade": trade,
            "side": side,
            "character": character,
            "other": other,
            "form": form,
            "coins": CoinSummary(owned=coin_balance(character), held=held_coins(character, trade)),
            "offer_rows": _offer_rows(character, trade, form),
        },
    )


@club_member_required
@require_POST
def approve(request, club_slug, pk):
    trade, side = _get_trade(request, pk)
    try:
        approve_trade(trade, side, request.user)
    except TradeError as err:
        messages.error(request, str(err))
    else:
        if trade.status == Trade.Status.COMPLETED:
            messages.success(request, "Trade completed.")
        else:
            messages.success(request, "You approved the trade.")
    return redirect("trades:detail", club_slug=club_slug, pk=trade.pk)
