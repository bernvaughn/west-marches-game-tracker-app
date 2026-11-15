from django.db.models import Q
from django.db.models.functions import Lower
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required, is_club_admin
from accounts.scoping import club_get_object_or_404
from items.magic_types import MagicType
from items.rarity import GROUPS
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
    buy_price,
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

# Filter options for the street filter bar
ITEM_TYPE_CHOICES = [
    ("", "All types"),
    ("magic_weapon", "Weapon"),
    ("magic_armor", "Armor"),
    ("magic_potion", "Potion"),
    ("magic_scroll", "Scroll"),
    ("magic_ring", "Ring"),
    ("magic_rod", "Rod"),
    ("magic_staff", "Staff"),
    ("magic_wand", "Wand"),
    ("magic_wondrous", "Wondrous item"),
    ("everyday_trivial", "Trivial"),
    ("everyday_cheap", "Cheap"),
    ("everyday_standard", "Standard"),
    ("everyday_fine", "Fine"),
    ("everyday_luxury", "Luxury"),
    ("everyday_exotic", "Exotic"),
    ("special", "Special"),
]

SORT_CHOICES = [
    ("distance", "Distance (street order)"),
    ("price_low", "Price: low to high"),
    ("price_high", "Price: high to low"),
    ("stock_high", "Stock: high to low"),
]


def _filter_shops(shops, item_type_filter, sort_by, show_buying_junk, character):
    """Apply filters and sorting to shops."""
    if not shops:
        return shops
    
    # Filter by item type
    if item_type_filter:
        if item_type_filter.startswith("magic_"):
            magic_type = item_type_filter.replace("magic_", "")
            shop_ids = ShopStock.objects.filter(
                shop__in=shops,
                item__retired=False,
                item__magic_type=magic_type,
            ).exclude(quantity=0).values_list("shop_id", flat=True).distinct()
            shops = [s for s in shops if s.id in shop_ids]
        elif item_type_filter.startswith("everyday_"):
            rarity = item_type_filter.replace("everyday_", "")
            shop_ids = ShopStock.objects.filter(
                shop__in=shops,
                item__retired=False,
                item__rarity=rarity,
            ).exclude(quantity=0).values_list("shop_id", flat=True).distinct()
            shops = [s for s in shops if s.id in shop_ids]
        elif item_type_filter == "special":
            shop_ids = ShopStock.objects.filter(
                shop__in=shops,
                item__retired=False,
                item__rarity="special",
            ).exclude(quantity=0).values_list("shop_id", flat=True).distinct()
            shops = [s for s in shops if s.id in shop_ids]
    
    # Filter: show only shops buying my junk
    if show_buying_junk and character:
        junk = junk_rows(character)
        if junk:
            junk_item_ids = [j.item_id for j in junk]
            # Find shops that have a buy_percent set for any of these items
            shop_ids = ShopStock.objects.filter(
                shop__in=shops,
                item_id__in=junk_item_ids,
                buy_percent__isnull=False,
            ).values_list("shop_id", flat=True).distinct()
            # Also include shops that have the default buy_percent > 0
            default_buy_shops = [s.id for s in shops if s.buy_percent > 0]
            all_shop_ids = set(shop_ids) | set(default_buy_shops)
            shops = [s for s in shops if s.id in all_shop_ids]
    
    # Apply sorting
    if sort_by == "price_low" or sort_by == "price_high":
        # For price sorting, we need a representative price - use average price of items in stock
        shop_prices = {}
        for shop in shops:
            stocks = ShopStock.objects.filter(shop=shop, item__retired=False).exclude(quantity=0)
            if stocks.exists():
                avg_price = sum(sell_price(s) for s in stocks) / stocks.count()
                shop_prices[shop.id] = avg_price
            else:
                shop_prices[shop.id] = 0
        reverse = sort_by == "price_high"
        shops = sorted(shops, key=lambda s: shop_prices.get(s.id, 0), reverse=reverse)
    elif sort_by == "stock_high":
        # Sort by total stock quantity (high to low)
        shop_stock_totals = {}
        for shop in shops:
            total = ShopStock.objects.filter(shop=shop, item__retired=False).exclude(quantity=0).count()
            shop_stock_totals[shop.id] = total
        shops = sorted(shops, key=lambda s: shop_stock_totals.get(s.id, 0), reverse=True)
    # distance (street order) is the default, no re-sorting needed
    
    return shops


def _compute_best_buy_prices(club, character, open_shops_list):
    """Compute best buy price for each junk item across all open shops."""
    if not character:
        return {}
    junk = junk_rows(character)
    if not junk:
        return {}
    
    junk_item_ids = [j.item_id for j in junk]
    best_prices = {}
    
    for shop in open_shops_list:
        for item_id in junk_item_ids:
            price = buy_price(shop, item_id)
            if price > 0:
                if item_id not in best_prices or price > best_prices[item_id][0]:
                    best_prices[item_id] = (price, shop)
    
    return best_prices


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
    today = timezone.localdate()
    open_shops_list = list(ordered_shops(open_shops(club, today)))
    
    # Get filter parameters from request
    item_type_filter = request.GET.get("item_type", "")
    sort_by = request.GET.get("sort", "distance")
    show_buying_junk = request.GET.get("buying_junk") == "1"
    
    character = selected_character(request)
    
    # Apply filters and sorting
    filtered_shops = _filter_shops(open_shops_list, item_type_filter, sort_by, show_buying_junk, character)
    
    stalls = street_stalls(club)
    lots = street_lots(
        filtered_shops,
        stalls,
        min_gap=club.street_min_gap,
        max_gap=club.street_max_gap,
        stall_gap=club.street_stall_gap,
    )
    
    # Compute best buy prices for junk items
    best_buy_prices = _compute_best_buy_prices(club, character, open_shops_list)
    
    context = {
        "shops": filtered_shops,
        "stalls": stalls,
        "lots": lots,
        "item_type_filter": item_type_filter,
        "sort_by": sort_by,
        "show_buying_junk": show_buying_junk,
        "item_type_choices": ITEM_TYPE_CHOICES,
        "sort_choices": SORT_CHOICES,
        "best_buy_prices": best_buy_prices,
    }
    
    # Check if this is an HTMX request for the street fragment
    if request.htmx:
        return render(request, "shops/browse/_street_fragment.html", context)
    
    return render(request, "shops/browse/index.html", context)


def _inventory_context(request, shop, best_buy_prices=None):
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
    
    # Add best buy prices for junk items
    if best_buy_prices is not None:
        for row in priced:
            if row["item"].id in best_buy_prices:
                row["best_price"] = best_buy_prices[row["item"].id][0]
                row["best_shop"] = best_buy_prices[row["item"].id][1]
    
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
    character = selected_character(request)
    open_shops_list = list(ordered_shops(open_shops(request.club, timezone.localdate())))
    best_buy_prices = _compute_best_buy_prices(request.club, character, open_shops_list)
    context = {"shop": shop, "is_open": open_now, "rows": _visible_rows(shop)}
    context.update(_inventory_context(request, shop, best_buy_prices))
    return render(request, "shops/browse/detail.html", context)


@club_member_required
def stock_fragment(request, club_slug, shop_id):
    shop, _ = _load_shop(request, shop_id)
    return render(request, "shops/browse/_stock.html", {"shop": shop, "rows": _visible_rows(shop)})
