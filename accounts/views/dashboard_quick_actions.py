"""Quick action views for dashboard: Sell Junk and Buy Potions modals."""

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from accounts.dashboard_providers import get_healing_potion_stock
from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from ledger.coins import format_coins
from player_characters.junk import junk_rows
from player_characters.selection import selected_character
from quests.services import needed_by_open_quests
from shops.buying import buy as buy_service
from shops.forms.buy import BuyForm
from shops.models import ShopStock
from shops.selling import sell_many
from shops.services import is_open, open_shops, percent_price, sell_price


@club_member_required
def quick_action_sell_junk(request, club_slug):
    """Modal partial for selling all junk to the best available shop."""
    club = request.club
    character = selected_character(request)
    if character is None:
        raise Http404("No character selected.")

    # Find the best open shop for selling junk (highest buy percent, first by street order)
    today = timezone.localdate()
    open_shop_qs = open_shops(club, today).order_by(
        "-buy_percent", "street_position", "name", "keeper_name", "id"
    )
    shop = open_shop_qs.first()
    if shop is None:
        raise Http404("No open shops available.")

    if not is_open(shop, today):
        raise Http404("Shop is closed.")

    error, posted = None, None
    if request.method == "POST":
        lines, error, posted = _parse_sell(request.POST, character, shop)
        if error is None:
            try:
                entries = sell_many(character, shop, lines, actor=request.user)
            except Exception as exc:
                error = str(exc)
            else:
                total = sum(
                    line.coins for entry in entries for line in entry.lines.all() if line.coins
                )
                messages.success(request, f"Sold junk to {shop} for {format_coins(total)}.")
                dashboard_url = reverse("accounts:player_dashboard", args=[club_slug])
                if is_htmx(request):
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = dashboard_url
                    return response
                return redirect(dashboard_url)
    elif request.GET.get("recalc"):
        _, _, posted = _parse_sell(request.GET, character, shop)

    rows = _rows_sell(character, shop, posted)
    return render_modal_or_page(
        request,
        "accounts/modals/_sell_junk.html",
        "accounts/modals/sell_junk.html",
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


def _rows_sell(character, shop, posted=None):
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


def _parse_sell(data, character, shop):
    """Return (lines, error, posted) from form data."""
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
        error = "Tick at least one item."
    return lines, error, posted


@club_member_required
def quick_action_buy_potions(request, club_slug):
    """Modal partial for buying healing potions from open shops."""
    club = request.club
    character = selected_character(request)
    if character is None:
        raise Http404("No character selected.")

    today = timezone.localdate()

    # Get all healing potions from open shops with stock > 0
    stock_qs = get_healing_potion_stock(club, today)

    error = None
    selected_stock_id = None
    stock_data = []

    for stock in stock_qs:
        if not is_open(stock.shop, today) or stock.item.retired:
            continue
        price = sell_price(stock)
        available = stock.quantity if stock.quantity is not None else 999
        if available <= 0:
            continue
        stock_data.append(
            {
                "stock": stock,
                "price": price,
                "available": available,
            }
        )
        if selected_stock_id is None:
            selected_stock_id = stock.pk

    if not stock_data:
        # No potions available - this shouldn't happen if should_show works, but handle it
        return render_modal_or_page(
            request,
            "accounts/modals/_buy_potions.html",
            "accounts/modals/buy_potions.html",
            {"character": character, "stock_data": [], "error": "No healing potions available."},
        )

    selected_stock = None
    form = None
    quantity = 1
    total = 0
    before = None
    after = None
    short = False

    if request.method == "POST":
        selected_stock_id = request.POST.get("stock_id")
        if selected_stock_id:
            shop_pks = stock_qs.values_list("shop", flat=True)
            selected_stock = club_get_object_or_404(
                request, ShopStock, pk=selected_stock_id, shop__in=shop_pks
            )
            price = sell_price(selected_stock)
            available = selected_stock.quantity if selected_stock.quantity is not None else 999
            form = BuyForm(request.POST, max_quantity=available)
            if form.is_valid():
                quantity = form.cleaned_data["quantity"]
                try:
                    entry = buy_service(character, selected_stock, quantity, actor=request.user)
                except Exception as exc:
                    error = str(exc)
                else:
                    messages.success(request, entry.note)
                    dashboard_url = reverse("accounts:player_dashboard", args=[club_slug])
                    if is_htmx(request):
                        response = HttpResponse(status=204)
                        response["HX-Redirect"] = dashboard_url
                        return response
                    return redirect(dashboard_url)
    else:
        # GET - check for stock_id in query params or use first
        selected_stock_id = request.GET.get("stock_id", selected_stock_id)
        if selected_stock_id:
            shop_pks = stock_qs.values_list("shop", flat=True)
            selected_stock = club_get_object_or_404(
                request, ShopStock, pk=selected_stock_id, shop__in=shop_pks
            )
        else:
            selected_stock = stock_data[0]["stock"]
        price = sell_price(selected_stock)
        available = selected_stock.quantity if selected_stock.quantity is not None else 999
        form = BuyForm(max_quantity=available)

    # Calculate totals for display
    from ledger.services import available_coins

    before = available_coins(character)
    price = sell_price(selected_stock)
    total = price * quantity
    after = before - total
    short = after < 0

    # Refresh stock data with selected flag
    for sd in stock_data:
        sd["selected"] = sd["stock"].pk == selected_stock.pk
        sd["price"] = sell_price(sd["stock"])
        sd["available"] = sd["stock"].quantity if sd["stock"].quantity is not None else 999

    return render_modal_or_page(
        request,
        "accounts/modals/_buy_potions.html",
        "accounts/modals/buy_potions.html",
        {
            "character": character,
            "stock_data": stock_data,
            "selected_stock": selected_stock,
            "price": price,
            "form": form,
            "error": error,
            "quantity": quantity,
            "total": total,
            "before": before,
            "after": after,
            "short": short,
            "selected_stock_id": selected_stock_id,
        },
    )
