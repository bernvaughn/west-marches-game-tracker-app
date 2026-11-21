from django.contrib import messages
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from accounts.htmx import htmx_or_redirect, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.stacked import unit_label
from ledger.coins import format_coins
from player_characters.junk import junk_rows
from player_characters.life import sell_block_reason, LifeError
from player_characters.selection import selected_character
from quests.services import needed_by_open_quests
from shops.models import Shop
from shops.selling import sale_total, sell_many
from shops.services import ShopError, is_open, open_shops
from shops.views.browse import add_recent_shop

NONE_TICKED = "Tick at least one item."


@club_member_required
def pick_shop(request, club_slug):
    """Pick a shop for selling junk -- redirects to sell_junk for that shop."""
    character = selected_character(request)
    if character is None:
        raise Http404("No character selected.")
    today = timezone.localdate()
    open_shop_list = list(open_shops(request.club, today).order_by("street_position", "name"))
    if not open_shop_list:
        return render_modal_or_page(
            request,
            "shops/sell/_shop_picker_modal.html",
            "shops/sell/shop_pickers_page.html",
            {"character": character, "open_shops": [], "no_shops": True},
        )
    if len(open_shop_list) == 1:
        shop = open_shop_list[0]
        shop_url = reverse("shops:sell_junk", args=[club_slug, shop.pk])
        return htmx_or_redirect(request, shop_url)
    return render_modal_or_page(
        request,
        "shops/sell/_shop_picker_modal.html",
        "shops/sell/shop_pickers_page.html",
        {"character": character, "open_shops": open_shop_list, "no_shops": False},
    )


def _rows(character, shop, posted=None):
    """Junk rows with line total, quest warning and tick state."""
    rows = junk_rows(character)
    needs = needed_by_open_quests(character) if rows else {}
    out = []
    for r in rows:
        quests = needs.get(r.item.pk, [])
        quantity = r.quantity
        if posted is not None:
            quantity = posted["quantities"].get(r.item.pk, quantity)
        line_total = sale_total(shop, r.item, quantity)
        ticked = not quests
        if posted is not None:
            ticked = str(r.item.pk) in posted["ticked"]
        out.append(
            {
                "item": r.item,
                "junk": r.quantity,
                "line_total": line_total,
                "pays_zero": line_total == 0,
                "quests": quests,
                "ticked": ticked,
                "quantity": quantity,
            }
        )
    return out


def _parse(data, character, shop):
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
        if row.item.is_stacked and sale_total(shop, row.item, quantity) == 0:
            unit_text = unit_label(row.item, quantity)
            message = f"{unit_text} is worth less than 1 cp here. Set it aside instead."
            return ([], message, posted)
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
        lines, error, posted = _parse(request.POST, character, shop)
        if error is None:
            try:
                entries = sell_many(character, shop, lines, actor=request.user)
            except ShopError as exc:
                error = str(exc)
            except LifeError as exc:
                error = str(exc)
            else:
                total = sum(
                    line.coins for entry in entries for line in entry.lines.all() if line.coins
                )
                messages.success(request, f"Sold junk to {shop} for {format_coins(total)}.")
                add_recent_shop(request, shop.pk)
                shop_url = reverse("shops:detail", args=[club_slug, shop.pk])
                # A full reload shows the "Sold junk" message with the total.
                return htmx_or_redirect(request, shop_url, trigger="junkChanged")
    elif request.GET.get("recalc") and character is not None:
        # htmx asks again as ticks and quantities change, so the total follows them.
        _, _, posted = _parse(request.GET, character, shop)
    if error is None and request.method != "POST":
        error = sell_block_reason(character)
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
                r["line_total"] for r in rows if r["ticked"] and 1 <= r["quantity"] <= r["junk"]
            ),
        },
    )
