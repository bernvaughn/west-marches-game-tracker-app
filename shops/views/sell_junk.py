from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from ledger.coins import format_coins
from player_characters.junk import junk_rows
from player_characters.selection import selected_character
from quests.services import needed_by_open_quests
from shops.models import Shop, ShopStock
from shops.selling import sell_many
from shops.services import ShopError, is_open, percent_price

NONE_TICKED = "Tick at least one item."


def _rows(character, shop, posted=None):
    """Junk rows with price, line total, quest warning and tick state."""
    rows = junk_rows(character)
    overrides = dict(
        ShopStock.objects.filter(
            shop=shop, item__in=[r.item for r in rows], buy_percent__isnull=False
        ).values_list("item_id", "buy_percent")
    )
    needs = needed_by_open_quests(character) if rows else {}
    out = []
    for r in rows:
        price = percent_price(r.item.value_cp, overrides.get(r.item.pk, shop.buy_percent))
        quests = needs.get(r.item.pk, [])
        ticked, quantity = not quests, r.quantity
        if posted is not None:
            ticked = str(r.item.pk) in posted["ticked"]
            quantity = posted["quantities"].get(r.item.pk, r.quantity)
        out.append(
            {
                "item": r.item,
                "junk": r.quantity,
                "price": price,
                "quests": quests,
                "ticked": ticked,
                "quantity": quantity,
            }
        )
    return out


def _parse(data, character):
    """Return (lines, error, posted) from form data. A bad id or quantity refuses the sale."""
    junk = {r.item.pk: r for r in junk_rows(character)}
    ticked = data.getlist("item")
    quantities = {}
    for pk in junk:
        raw = data.get(f"qty_{pk}", "")
        if raw.strip().lstrip("-").isdigit():
            quantities[pk] = int(raw)
    posted = {"ticked": set(ticked), "quantities": quantities}
    lines, error = [], None
    for raw_id in ticked:
        if not raw_id.isdigit() or int(raw_id) not in junk:
            return [], "One of the ticked items is not in your junk.", posted
        pk = int(raw_id)
        row = junk[pk]
        quantity = quantities.get(pk)
        if quantity is None or not 1 <= quantity <= row.quantity:
            return [], f"{row.item}: choose a quantity from 1 to {row.quantity}.", posted
        lines.append((row.item, quantity))
    if not lines:
        error = NONE_TICKED
    return lines, error, posted


@club_member_required
def sell_junk(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    if not is_open(shop, timezone.localdate()):
        raise Http404("Shop is closed.")
    character = selected_character(request)
    error, posted = None, None
    if request.method == "POST" and character is not None:
        lines, error, posted = _parse(request.POST, character)
        if error is None:
            try:
                entries = sell_many(character, shop, lines, actor=request.user)
            except ShopError as exc:
                error = str(exc)
            else:
                total = sum(
                    line.coins for entry in entries for line in entry.lines.all() if line.coins
                )
                messages.success(request, f"Sold junk to {shop} for {format_coins(total)}.")
                shop_url = reverse("shops:detail", args=[club_slug, shop.pk])
                if is_htmx(request):
                    # A full reload shows the "Sold junk" message with the total.
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = shop_url
                    return response
                return redirect(shop_url)
    elif request.GET.get("recalc") and character is not None:
        # htmx asks again as ticks and quantities change, so the total follows them.
        _, _, posted = _parse(request.GET, character)
    rows = _rows(character, shop, posted) if character is not None else []
    return render_modal_or_page(
        request,
        "shops/sell/_junk_modal.html",
        "shops/sell/junk.html",
        {
            "shop": shop,
            "character": character,
            "rows": rows,
            "error": error,
            "total": sum(
                r["price"] * r["quantity"]
                for r in rows
                if r["ticked"] and 1 <= r["quantity"] <= r["junk"]
            ),
        },
    )
