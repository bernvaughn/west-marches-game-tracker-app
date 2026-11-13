from django.db.models.functions import Lower
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required, is_club_admin
from accounts.scoping import club_get_object_or_404
from player_characters.inventory import coin_summary, inventory_rows
from player_characters.junk import junk_rows, junk_value, junk_value_at
from player_characters.models import Character
from player_characters.player_shop import has_listing
from player_characters.selection import selected_character
from shops.models import Shop, ShopStock
from shops.services import (
    is_open,
    open_shops,
    ordered_shops,
    percent_price,
    sell_price,
    shop_sort_key,
)


def _load_shop(request, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    open_now = is_open(shop, timezone.localdate())
    if not open_now and not is_club_admin(request.user, request.club):
        raise Http404
    return shop, open_now


def _visible_rows(shop):
    stocks = (
        ShopStock.objects.filter(shop=shop, item__retired=False)
        .exclude(quantity=0)
        .select_related("item", "shop")
        .order_by("item__name")
    )
    rows = list(stocks)
    for stock in rows:
        stock.price = sell_price(stock)
    return rows


STREET_ROW = 8
SHAPE_KEYS = [v for v, _ in Shop.Building.choices]


def street_lots(shops, stalls=(), *, min_gap=0, max_gap=2, stall_gap=1, per_row=STREET_ROW):
    """Lay out the street: club shops, then player stalls, padded to whole rows.

    Each lot is {"shop", "stall", "shape"}; empty lots have neither.
    """
    shops = sorted(shops, key=shop_sort_key)
    stalls = list(stalls)
    if not shops and not stalls:
        return []
    items, prev = [], -1
    for s in shops:
        if prev < 0 and not items:
            gap = min(s.street_position, max_gap)
        else:
            gap = min(max(max(s.street_position - prev - 1, 0), min_gap), max_gap)
        items.extend([(None, None)] * gap)
        items.append((s, None))
        prev = s.street_position
    if stalls and shops:
        items.extend([(None, None)] * max(stall_gap, min_gap))
    for i, c in enumerate(stalls):
        if i:
            items.extend([(None, None)] * min_gap)
        items.append((None, c))
    size = -(-len(items) // per_row) * per_row
    items.extend([(None, None)] * (size - len(items)))
    return [
        {"shop": s, "stall": c, "shape": SHAPE_KEYS[(i * 7 + 3) % len(SHAPE_KEYS)]}
        for i, (s, c) in enumerate(items)
    ]


def street_stalls(club):
    """Open player shops in this club with something listed, by name then id."""
    characters = Character.objects.filter(club=club, shop_open=True).order_by(Lower("name"), "id")
    return [c for c in characters if has_listing(c)]


@club_member_required
def index(request, club_slug):
    club = request.club
    shops = list(ordered_shops(open_shops(club, timezone.localdate())))
    stalls = street_stalls(club)
    lots = street_lots(
        shops,
        stalls,
        min_gap=club.street_min_gap,
        max_gap=club.street_max_gap,
        stall_gap=club.street_stall_gap,
    )
    return render(
        request, "shops/browse/index.html", {"shops": shops, "stalls": stalls, "lots": lots}
    )


def _inventory_context(request, shop):
    character = selected_character(request)
    if character is None:
        return {"inventory_character": None}
    rows = inventory_rows(character)
    overrides = dict(
        ShopStock.objects.filter(
            shop=shop, item__in=[r.item for r in rows], buy_percent__isnull=False
        ).values_list("item_id", "buy_percent")
    )
    priced = [
        {
            "item": r.item,
            "owned": r.owned,
            "available": r.available,
            "price": percent_price(r.item.value_cp, overrides.get(r.item.pk, shop.buy_percent)),
        }
        for r in rows
    ]
    junk = junk_rows(character)
    return {
        "inventory_has_junk": bool(junk),
        "inventory_junk_value": junk_value(character, junk),
        "inventory_junk_value_at": junk_value_at(character, shop, junk),
        "inventory_character": character,
        "inventory_coins": coin_summary(character),
        "inventory_rows": priced,
        "inventory_has_holds": any(r.held for r in rows),
    }


@club_member_required
def shop_detail(request, club_slug, shop_id):
    shop, open_now = _load_shop(request, shop_id)
    context = {"shop": shop, "is_open": open_now, "rows": _visible_rows(shop)}
    context.update(_inventory_context(request, shop))
    return render(request, "shops/browse/detail.html", context)


@club_member_required
def stock_fragment(request, club_slug, shop_id):
    shop, _ = _load_shop(request, shop_id)
    return render(request, "shops/browse/_stock.html", {"shop": shop, "rows": _visible_rows(shop)})
