from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.coins import format_coins
from ledger.services import InsufficientItems, available_items
from player_characters.selection import selected_character
from shops.forms.sell import SellForm
from shops.models import Shop
from shops.selling import sell as do_sell
from shops.services import ShopError, buy_price, is_open


@club_member_required
def sell(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    if not is_open(shop, timezone.localdate()):
        raise Http404("Shop is closed.")

    club = request.club
    character = selected_character(request)

    items = Item.objects.for_club(club)

    if request.method == "POST":
        item_id = request.POST.get("item", "")
        if not item_id.isdigit():
            raise Http404("No such item.")
        club_get_object_or_404(request, Item, pk=int(item_id))
        form = SellForm(request.POST, items=items)
        error = None
        if character is None:
            error = "You have no character in this club."
        elif form.is_valid():
            item = form.cleaned_data["item"]
            quantity = form.cleaned_data["quantity"]
            try:
                entry = do_sell(character, shop, item, quantity, actor=request.user)
            except InsufficientItems:
                error = f"Not enough {item} available to sell."
            except ShopError as e:
                error = str(e)
            else:
                total = sum(line.coins for line in entry.lines.all())
                messages.success(
                    request, f"Sold {quantity} × {item} to {shop} for {format_coins(total)}."
                )
                return redirect("shops:detail", club_slug=club.slug, shop_id=shop.pk)
        else:
            error = "Check the form: " + "; ".join(
                f"{k}: {' '.join(v)}" for k, v in form.errors.items()
            )
        messages.error(request, error)
    else:
        form = SellForm(items=items)

    rows = []
    if character is not None:
        names = {
            i.pk: i
            for i in Item.objects.for_club(club).filter(pk__in=available_items(character).keys())
        }
        for item_id, qty in available_items(character).items():
            item = names.get(item_id)
            if item is not None:
                rows.append({"item": item, "quantity": qty, "price": buy_price(shop, item)})
        rows.sort(key=lambda r: r["item"].name)

    return render(
        request,
        "shops/sell/sell.html",
        {
            "shop": shop,
            "character": character,
            "rows": rows,
            "form": form,
        },
    )
