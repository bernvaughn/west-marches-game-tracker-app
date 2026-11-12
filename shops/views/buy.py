from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from ledger.coins import format_coins
from ledger.services import InsufficientFunds, available_coins
from player_characters.selection import selected_character
from shops.buying import buy as buy_service
from shops.forms.buy import BuyForm
from shops.models import Shop, ShopStock
from shops.services import ShopError, is_open, sell_price


@club_member_required
def buy(request, club_slug, shop_id, stock_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    stock = club_get_object_or_404(request, ShopStock, pk=stock_id, shop=shop)
    if not is_open(shop, timezone.localdate()) or stock.item.retired:
        raise Http404
    character = selected_character(request)
    unit_price = sell_price(stock)
    error = None
    if stock.quantity == 0:
        error = "Already sold: someone bought the last one."

    if request.method == "POST":
        form = BuyForm(request.POST, max_quantity=stock.quantity)
        if character is not None and form.is_valid():
            quantity = form.cleaned_data["quantity"]
            try:
                entry = buy_service(character, stock, quantity, actor=request.user)
            except InsufficientFunds:
                error = (
                    f"{character} cannot afford this: needs "
                    f"{format_coins(unit_price * quantity)}, has "
                    f"{format_coins(available_coins(character))} available."
                )
            except ShopError as exc:
                error = str(exc)
            else:
                messages.success(request, entry.note)
                return redirect("shops:detail", club_slug=club_slug, shop_id=shop.pk)
    else:
        form = BuyForm(max_quantity=stock.quantity)

    stock.refresh_from_db()
    return render(
        request,
        "shops/buy/buy.html",
        {
            "shop": shop,
            "stock": stock,
            "price": unit_price,
            "form": form,
            "error": error,
            "character": character,
            "available": available_coins(character) if character else None,
            "sold_out": stock.quantity == 0,
        },
    )
