from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.coins import format_coins
from ledger.services import InsufficientFunds, available_coins
from player_characters.access import owns_character
from player_characters.inventory import coin_summary, inventory_rows
from player_characters.models import Character
from player_characters.player_shop import PlayerShopError, buy_from, has_listing, listed_rows
from player_characters.selection import selected_character
from shops.forms.buy import BuyForm


def _load_stall(request, character_id):
    seller = club_get_object_or_404(request, Character, pk=character_id)
    is_own = owns_character(request.user, seller)
    if not is_own and not has_listing(seller):
        raise Http404("No shop here.")
    return seller, is_own


@club_member_required
def player_shop(request, club_slug, character_id):
    seller, is_own = _load_stall(request, character_id)
    buyer = selected_character(request)
    rows = listed_rows(seller)
    inventory = inventory_rows(buyer) if buyer else []
    return render(
        request,
        "shops/player/detail.html",
        {
            "seller": seller,
            "rows": rows,
            "is_own": is_own,
            "buyer": buyer,
            "inventory_rows": inventory,
            "inventory_coins": coin_summary(buyer) if buyer else None,
            "inventory_has_holds": any(r.held for r in inventory),
        },
    )


@club_member_required
def buy(request, club_slug, character_id, item_id):
    seller, is_own = _load_stall(request, character_id)
    item = club_get_object_or_404(request, Item, pk=item_id)
    listed = next((r.quantity for r in listed_rows(seller) if r.item.pk == item.pk), 0)
    if not is_own and not listed:
        raise Http404("Not listed.")
    buyer = selected_character(request)
    unit_price = item.value_cp
    error = None
    if is_own or (buyer is not None and buyer.owner_id == seller.owner_id):
        error = "This is your shop."
    max_quantity = max(listed, 1)
    stall_url = reverse(
        "shops:player_shop", kwargs={"club_slug": club_slug, "character_id": seller.pk}
    )

    if request.method == "POST":
        form = BuyForm(request.POST, max_quantity=max_quantity)
        if error is None and buyer is not None and form.is_valid():
            quantity = form.cleaned_data["quantity"]
            try:
                entry = buy_from(buyer, seller, item, quantity, actor=request.user)
            except InsufficientFunds:
                error = (
                    f"{buyer} cannot afford this: needs "
                    f"{format_coins(unit_price * quantity)}, has "
                    f"{format_coins(available_coins(buyer))} available."
                )
            except PlayerShopError as exc:
                error = str(exc)
            else:
                messages.success(request, entry.note)
                target = (
                    stall_url
                    if has_listing(seller)
                    else reverse("shops:index", kwargs={"club_slug": club_slug})
                )
                if is_htmx(request):
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = target
                    return response
                return redirect(target)
    elif "quantity" in request.GET:
        form = BuyForm(request.GET, max_quantity=max_quantity)
    else:
        form = BuyForm(max_quantity=max_quantity)

    quantity = 1
    if form.is_bound and form.is_valid():
        quantity = form.cleaned_data["quantity"]
    elif form.is_bound:
        try:
            quantity = max(int(form.data.get("quantity", 1)), 0)
        except (TypeError, ValueError):
            quantity = 0
    before = available_coins(buyer) if buyer else None
    total = unit_price * quantity
    after = before - total if buyer else None
    return render_modal_or_page(
        request,
        "shops/player/_confirm.html",
        "shops/player/buy.html",
        {
            "seller": seller,
            "item": item,
            "listed": listed,
            "price": unit_price,
            "quantity": quantity,
            "total": total,
            "before": before,
            "after": after,
            "short": buyer is not None and after < 0,
            "form": form,
            "error": error,
            "buyer": buyer,
            "coins": coin_summary(buyer) if buyer else None,
            "stall_url": stall_url,
            "can_buy": error is None and listed > 0,
            "max_quantity": max_quantity,
        },
    )
