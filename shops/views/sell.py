from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.coins import format_coins
from ledger.services import InsufficientItems, available_items, held_items
from player_characters.junk import junk_rows, reduce_junk
from player_characters.selection import selected_character
from shops.models import Shop
from shops.selling import sell as do_sell
from shops.services import ShopError, buy_price, is_open


@club_member_required
def sell_item(request, club_slug, shop_id, item_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    if not is_open(shop, timezone.localdate()):
        raise Http404("Shop is closed.")
    item = club_get_object_or_404(request, Item, pk=item_id)
    club = request.club
    target = reverse("shops:detail", kwargs={"club_slug": club.slug, "shop_id": shop.pk})
    if request.method != "POST":
        return redirect(target)

    character = selected_character(request)
    error = None
    try:
        quantity = int(request.POST.get("quantity", ""))
        if quantity < 1:
            raise ValueError
    except ValueError:
        quantity = 0
        error = "Enter a quantity of 1 or more."
    if error is None and character is None:
        error = "You have no character in this club."
    if error is None:
        available = available_items(character).get(item.pk, 0)
        junk = {r.item.pk: r.quantity for r in junk_rows(character)}
        if quantity > available:
            error = f"Not enough {item} available to sell."
        elif quantity > junk.get(item.pk, 0) and request.POST.get("confirmed") != "1":
            unit = buy_price(shop, item)
            return render_modal_or_page(
                request,
                "shops/sell/_confirm_modal.html",
                "shops/sell/confirm.html",
                {
                    "shop": shop,
                    "character": character,
                    "item": item,
                    "quantity": quantity,
                    "price": unit,
                    "total": unit * quantity,
                    "junk_quantity": junk.get(item.pk, 0),
                    "held": held_items(character).get(item.pk, 0),
                    "available": available,
                },
            )
        else:
            try:
                with transaction.atomic():
                    entry = do_sell(character, shop, item, quantity, actor=request.user)
                    reduce_junk(character, {item: quantity})
            except InsufficientItems:
                error = f"Not enough {item} available to sell."
            except ShopError as e:
                error = str(e)
            else:
                total = sum(line.coins for line in entry.lines.all())
                messages.success(
                    request, f"Sold {quantity} × {item} to {shop} for {format_coins(total)}."
                )
    if error:
        messages.error(request, error)
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = target
        return response
    return redirect(target)
