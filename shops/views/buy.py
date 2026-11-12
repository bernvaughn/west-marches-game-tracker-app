from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from ledger.coins import format_coins
from ledger.services import InsufficientFunds, available_coins
from player_characters.junk import junk_value
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
                if is_htmx(request):
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = reverse(
                        "shops:detail", kwargs={"club_slug": club_slug, "shop_id": shop.pk}
                    )
                    return response
                return redirect("shops:detail", club_slug=club_slug, shop_id=shop.pk)
    elif "quantity" in request.GET:
        form = BuyForm(request.GET, max_quantity=stock.quantity)
    else:
        form = BuyForm(max_quantity=stock.quantity)

    stock.refresh_from_db()
    quantity = 1
    if form.is_bound and form.is_valid():
        quantity = form.cleaned_data["quantity"]
    elif form.is_bound:
        try:
            quantity = max(int(form.data.get("quantity", 1)), 0)
        except (TypeError, ValueError):
            quantity = 0
    before = available_coins(character) if character else None
    total = unit_price * quantity
    after = before - total if character else None
    return render_modal_or_page(
        request,
        "shops/buy/_confirm.html",
        "shops/buy/buy.html",
        {
            "quantity": quantity,
            "total": total,
            "before": before,
            "after": after,
            "short": character is not None and after < 0,
            "shop": shop,
            "stock": stock,
            "price": unit_price,
            "form": form,
            "error": error,
            "character": character,
            "junk_value": junk_value(character) if character else 0,
            "available": available_coins(character) if character else None,
            "sold_out": stock.quantity == 0,
        },
    )
