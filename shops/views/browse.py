from django.contrib.contenttypes.models import ContentType
from django.db.models.functions import Lower
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from accounts.htmx import render_modal_or_page
from accounts.mixins import (
    CharacterContextMixin,
    ClubContextMixin,
    ClubScopedMixin,
    PermissionMixin,
)
from accounts.permissions import club_member_required
from player_characters.models import Character
from player_characters.player_shop import has_listing
from player_characters.selection import selected_character
from shops.models import FavoriteShop, Shop, ShopStock
from shops.services import (
    is_open,
    open_shops,
    ordered_shops,
    percent_price,
    sell_price,
    shop_sort_key,
)

MAX_RECENT_SHOPS = 10


def add_recent_shop(request, shop_id):
    """Add a shop to the character's recent shops in session."""
    character = selected_character(request)
    if not character:
        return
    session_key = f"wm_recent_shops_{character.pk}"
    recent = list(request.session.get(session_key, []))
    # Remove if already present
    recent = [sid for sid in recent if sid != shop_id]
    # Add to front
    recent.insert(0, shop_id)
    # Limit to max
    if len(recent) > MAX_RECENT_SHOPS:
        recent = recent[:MAX_RECENT_SHOPS]
    request.session[session_key] = recent


def _load_shop(view, shop_id, is_club_admin):
    shop = view.get_club_object_or_404(Shop, pk=shop_id)
    open_now = is_open(shop, timezone.localdate())
    if not open_now and not is_club_admin:
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


def add_favorite_flags(lots, favorite_shop_ids, favorite_stall_ids):
    """Add is_favorite flag to each lot based on favorite IDs."""
    for lot in lots:
        if lot.get("shop"):
            lot["is_favorite"] = lot["shop"].pk in favorite_shop_ids
        elif lot.get("stall"):
            lot["is_favorite"] = lot["stall"].pk in favorite_stall_ids
        else:
            lot["is_favorite"] = False
    return lots


def street_stalls(club):
    """Open player shops in this club with something listed, by name then id."""
    characters = (
        Character.objects.for_club(club).filter(shop_open=True).order_by(Lower("name"), "id")
    )
    return [c for c in characters if has_listing(c)]


@method_decorator(club_member_required, name="dispatch")
class IndexView(ClubScopedMixin, CharacterContextMixin, ClubContextMixin, View):
    def get(self, request, club_slug):
        character = self.get_selected_character()

        # Get recent shop IDs from session storage
        recent_shop_ids = []
        favorite_shop_ids = set()
        favorite_stall_ids = set()
        if character:
            session_key = f"wm_recent_shops_{character.pk}"
            recent_shop_ids = request.session.get(session_key, [])
            # Get favorite shop IDs for current character
            shop_ct = ContentType.objects.get_for_model(Shop)
            stall_ct = ContentType.objects.get_for_model(Character)
            favorite_shop_ids = set(
                FavoriteShop.objects.for_club(self.club)
                .filter(character=character, content_type=shop_ct)
                .values_list("object_id", flat=True)
            )
            favorite_stall_ids = set(
                FavoriteShop.objects.for_club(self.club)
                .filter(character=character, content_type=stall_ct)
                .values_list("object_id", flat=True)
            )

        # Determine active tab
        active_tab = request.GET.get("tab", "all")

        shops_qs = ordered_shops(open_shops(self.club, timezone.localdate()))

        # Filter shops for "My Shops" tab
        if active_tab == "my_shops":
            if recent_shop_ids:
                shops_qs = shops_qs.filter(pk__in=recent_shop_ids)
            else:
                shops_qs = shops_qs.none()
        elif active_tab == "favorites":
            if favorite_shop_ids:
                shops_qs = shops_qs.filter(pk__in=favorite_shop_ids)
            else:
                shops_qs = shops_qs.none()

        shops = list(shops_qs)

        stalls = street_stalls(self.club)
        # Filter stalls for favorites tab
        if active_tab == "favorites":
            if favorite_stall_ids:
                stalls = [s for s in stalls if s.pk in favorite_stall_ids]
            else:
                stalls = []

        lots = street_lots(
            shops,
            stalls,
            min_gap=self.club.street_min_gap,
            max_gap=self.club.street_max_gap,
            stall_gap=self.club.street_stall_gap,
        )
        # Add favorite flags to lots
        lots = add_favorite_flags(lots, favorite_shop_ids, favorite_stall_ids)
        return render(
            request,
            "shops/browse/index.html",
            {
                "shops": shops,
                "stalls": stalls,
                "lots": lots,
                "recent_shop_ids": recent_shop_ids,
                "favorite_shop_ids": favorite_shop_ids,
                "favorite_stall_ids": favorite_stall_ids,
                "active_tab": active_tab,
                "character": character,
            },
        )


def _inventory_context(character, shop):
    if character is None:
        return {"inventory_character": None}
    from player_characters.inventory import coin_summary, inventory_rows
    from player_characters.junk import junk_rows, junk_value, junk_value_at

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


@method_decorator(club_member_required, name="dispatch")
class ShopDetailView(
    ClubScopedMixin, PermissionMixin, CharacterContextMixin, ClubContextMixin, View
):
    def get(self, request, club_slug, shop_id):
        is_admin = self.is_club_admin(request.user, self.club)
        shop, open_now = _load_shop(self, shop_id, is_admin)
        context = {"shop": shop, "is_open": open_now, "rows": _visible_rows(shop)}
        character = self.get_selected_character()
        context.update(_inventory_context(character, shop))
        return render_modal_or_page(
            request, "shops/browse/_detail_fragment.html", "shops/browse/detail.html", context
        )


@method_decorator(club_member_required, name="dispatch")
class StockFragmentView(ClubScopedMixin, PermissionMixin, ClubContextMixin, View):
    def get(self, request, club_slug, shop_id):
        is_admin = self.is_club_admin(request.user, self.club)
        shop, _ = _load_shop(self, shop_id, is_admin)
        return render(
            request, "shops/browse/_stock.html", {"shop": shop, "rows": _visible_rows(shop)}
        )


@method_decorator(club_member_required, name="dispatch")
class FavoriteToggleView(ClubScopedMixin, CharacterContextMixin, ClubContextMixin, View):
    """Toggle favorite for a shop or player stall via htmx POST."""

    def post(self, request, club_slug, shop_id=None, character_id=None):
        character = self.get_selected_character()
        if not character:
            return HttpResponse(status=403)

        # Determine if this is a club shop or player stall
        if shop_id is not None:
            # Club shop
            shop = self.get_club_object_or_404(Shop, pk=shop_id)
            content_object = shop
            object_type = "shop"
        elif character_id is not None:
            # Player stall
            stall = self.get_club_object_or_404(Character, pk=character_id)
            if not stall.shop_open or not has_listing(stall):
                raise Http404
            content_object = stall
            object_type = "stall"
        else:
            raise Http404

        # Toggle favorite
        ct = ContentType.objects.get_for_model(content_object)
        favorite, created = FavoriteShop.objects.get_or_create(
            character=character,
            content_type=ct,
            object_id=content_object.pk,
        )
        if not created:
            favorite.delete()
            is_favorite = False
            message = "Removed from favorites"
        else:
            is_favorite = True
            message = "Added to favorites"

        # Return updated star button partial
        context = {
            "is_favorite": is_favorite,
            "lot": {
                "shop": content_object if object_type == "shop" else None,
                "stall": content_object if object_type == "stall" else None,
            },
            "club": self.club,
            "character": character,
        }
        response = render(request, "shops/browse/_star_button.html", context)
        response["HX-Trigger"] = f'{{"toast": {{"message": "{message}", "type": "success"}}}}'
        return response
