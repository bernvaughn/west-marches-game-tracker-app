from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required, is_club_admin
from accounts.scoping import club_get_object_or_404
from player_characters.inventory import coin_summary, inventory_rows
from player_characters.junk import junk_rows, junk_value, junk_value_at
from player_characters.selection import selected_character
from shops.models import Shop, ShopStock
from shops.services import is_open, open_shops, percent_price, sell_price


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


def street_lots(shops, per_row=STREET_ROW):
    """Place open shops on numbered lots and pad the street to whole rows."""
    shops = sorted(shops, key=lambda s: (s.name, s.id))
    if not shops:
        return []
    cap = -(-len(shops) // per_row) * per_row + per_row
    counts = {}
    for s in shops:
        counts[s.street_position] = counts.get(s.street_position, 0) + 1
    placed, rest = {}, []
    for s in shops:
        if counts[s.street_position] == 1 and 0 <= s.street_position < cap:
            placed[s.street_position] = s
        else:
            rest.append(s)
    lot = 0
    for s in rest:
        while lot in placed:
            lot += 1
        placed[lot] = s
    size = -(-(max(placed) + 1) // per_row) * per_row
    return [
        {"shop": placed.get(i), "shape": SHAPE_KEYS[(i * 7 + 3) % len(SHAPE_KEYS)]}
        for i in range(size)
    ]


@club_member_required
def index(request, club_slug):
    shops = list(open_shops(request.club, timezone.localdate()))
    return render(request, "shops/browse/index.html", {"shops": shops, "lots": street_lots(shops)})


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
