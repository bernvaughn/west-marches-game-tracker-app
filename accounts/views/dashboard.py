"""Player dashboard view: contextual quick actions for between-session tasks."""

from dataclasses import dataclass

from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.dashboard_providers import get_provider, get_providers
from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_queryset
from downtime import services as downtime_services
from downtime.models import DowntimeAction
from ledger.services import available_items
from map.models import FoundMark, HexMap, Location, LocationCredit, TileVisit
from player_characters.inventory import coin_summary
from player_characters.junk import junk_rows, junk_value
from player_characters.models import Trade
from player_characters.selection import selected_character
from player_characters.trade_services import OPEN
from quests.models import Quest, QuestCompletion

# =============================================================================
# Dashboard Provider Classes
# =============================================================================


@dataclass
class TradesProvider:
    """Open trades with status."""

    key: str = "trades"
    order: int = 2
    template: str = "accounts/_dashboard_trades.html"

    def get_context(self, request, club, character, membership):
        trades_qs = club_queryset(request, Trade).filter(status__in=OPEN)
        my_trades = trades_qs.filter(
            Q(sender__owner=membership) | Q(receiver__owner=membership)
        ).select_related("sender__owner__user", "receiver__owner__user")

        open_trades_data = []
        for t in my_trades:
            if t.sender.owner_id == membership.id:
                other = t.receiver
                side = "sender"
            else:
                other = t.sender
                side = "receiver"
            open_trades_data.append({
                "trade": t,
                "other_character": other,
                "side": side,
                "status_display": t.get_status_display(),
            })

        trade_items = []
        for t in open_trades_data:
            trade_items.append({
                "label": f"Trade with {t['other_character'].name}",
                "url": reverse("trades:detail", args=[club.slug, t['trade'].pk]),
                "icon": "arrow-left-right",
                "subtext": t['status_display'],
            })
        if not trade_items:
            trade_items.append({
                "label": "Propose Trade",
                "url": reverse("trades:propose", args=[club.slug]),
                "icon": "plus",
                "subtext": "Start a new trade",
            })

        return {
            "open_trades": open_trades_data,
            "trade_items": trade_items,
        }

    def should_show(self, request, club, character, membership):
        return True


@dataclass
class QuestsProvider:
    """Ready-to-turn-in quests."""

    key: str = "quests"
    order: int = 3
    template: str = "accounts/_dashboard_quests.html"

    def get_context(self, request, club, character, membership):
        today = timezone.localdate()

        quests_qs = Quest.objects.for_club(club).prefetch_related(
            "requirements__item", "rewards__item"
        ).annotate(done=Count("completions"))

        have = available_items(character)
        my_completions = {
            row["quest"]: row["n"]
            for row in QuestCompletion.objects.filter(character=character)
            .values("quest")
            .annotate(n=Count("id"))
        }

        ready_quests = []
        for q in quests_qs:
            if not q.is_live_on(today):
                continue
            if q.max_completions is not None and q.done >= q.max_completions:
                continue
            if (
                q.max_per_character is not None
                and my_completions.get(q.pk, 0) >= q.max_per_character
            ):
                continue
            reqs = list(q.requirements.all())
            if reqs and all(have.get(r.item_id, 0) >= r.quantity for r in reqs):
                ready_quests.append(q)

        quest_items = []
        for q in ready_quests:
            quest_items.append({
                "label": q.name,
                "url": reverse("quests:detail", args=[club.slug, q.pk]),
                "icon": "check-circle",
                "subtext": "Ready to turn in",
            })
        if not quest_items:
            quest_items.append({
                "label": "Quest Board",
                "url": reverse("quests:index", args=[club.slug]),
                "icon": "scroll",
                "subtext": "Browse available quests",
            })

        return {
            "ready_quests": ready_quests,
            "quest_items": quest_items,
        }

    def should_show(self, request, club, character, membership):
        return True


@dataclass
class DowntimeProvider:
    """Available downtime actions."""

    key: str = "downtime"
    order: int = 4
    template: str = "accounts/_dashboard_downtime.html"

    def get_context(self, request, club, character, membership):
        today = timezone.localdate()
        downtime_balance = downtime_services.balance(character)

        live_actions = (
            DowntimeAction.objects.for_club(club)
            .live_on(today)
            .filter(entries__isnull=False)
            .distinct()
            .prefetch_related("entries__items__item")
        )

        downtime_cards = []
        for action in live_actions:
            reason = ""
            if downtime_balance < action.cost:
                reason = "Not enough downtime points."
            downtime_cards.append({
                "action": action,
                "cost": action.cost,
                "reason": reason,
            })

        downtime_items = []
        for d in downtime_cards:
            downtime_items.append({
                "label": d["action"].name,
                "url": reverse("downtime:play", args=[club.slug]),
                "icon": "clock",
                "subtext": f"Cost: {d['cost']} point{'s' if d['cost'] != 1 else ''}",
                "badge": "" if not d["reason"] else "disabled",
            })
        if not downtime_items:
            downtime_items.append({
                "label": "Downtime Actions",
                "url": reverse("downtime:play", args=[club.slug]),
                "icon": "clock",
                "subtext": "No actions available",
            })

        return {
            "downtime_balance": downtime_balance,
            "downtime_cards": downtime_cards,
            "downtime_items": downtime_items,
        }

    def should_show(self, request, club, character, membership):
        return True


class MapDashboardProvider:
    """Map section with Request Map Credit shortcut for uncredited visits."""

    key: str = "map"
    order: int = 5
    template: str = "accounts/_dashboard_map.html"

    def _get_uncredited_data(self, club, character):
        """Get maps with uncredited tiles for the character."""
        # Get all tile visits for this character
        visits = TileVisit.objects.for_club(club).filter(character=character).select_related("map")
        
        # Group visits by map
        map_visits = {}
        for visit in visits:
            if visit.map_id not in map_visits:
                map_visits[visit.map_id] = []
            map_visits[visit.map_id].append((visit.q, visit.r))
        
        if not map_visits:
            return [], 0, None
        
        # Get maps with visits
        maps_with_visits = (
            HexMap.objects.for_club(club)
            .filter(pk__in=map_visits.keys())
            .order_by("name")
        )
        
        maps_data = []
        total_uncredited = 0
        first_map_with_uncredited = None
        first_map_uncredited_tiles = None
        
        for hex_map in maps_with_visits:
            visited_positions = set(map_visits[hex_map.pk])
            
            # Get locations on visited tiles
            locations = Location.objects.for_club(club).filter(
                tile__map=hex_map,
                tile__q__in=[q for q, r in visited_positions],
                tile__r__in=[r for q, r in visited_positions],
            ).select_related("tile")
            
            # Check each location for missing credits
            map_uncredited_tiles = set()
            for loc in locations:
                pos = (loc.tile.q, loc.tile.r)
                if pos not in visited_positions:
                    continue
                
                # Check if character has credit for this location
                has_discovered = LocationCredit.objects.for_club(club).filter(
                    location=loc,
                    kind=LocationCredit.Kind.DISCOVERED,
                    characters=character
                ).exists()
                
                has_explored = LocationCredit.objects.for_club(club).filter(
                    location=loc,
                    kind=LocationCredit.Kind.EXPLORED,
                    characters=character
                ).exists()
                
                has_found = FoundMark.objects.for_club(club).filter(
                    location=loc,
                    character=character
                ).exists()
                
                # If any credit type is missing, this tile needs credit
                if not (has_discovered and has_explored and has_found):
                    map_uncredited_tiles.add(pos)
            
            uncredited_count = len(map_uncredited_tiles)
            if uncredited_count > 0:
                total_uncredited += uncredited_count
                maps_data.append({
                    "map": hex_map,
                    "uncredited_count": uncredited_count,
                })
                if first_map_with_uncredited is None:
                    first_map_with_uncredited = hex_map
                    first_map_uncredited_tiles = map_uncredited_tiles
        
        return maps_data, total_uncredited, (first_map_with_uncredited, first_map_uncredited_tiles)

    def get_context(self, request, club, character, membership):
        maps_data, total_uncredited, first_map_data = self._get_uncredited_data(club, character)
        
        # Build map items for the template (always show all maps)
        all_maps = HexMap.objects.for_club(club).order_by("name")
        map_items = [
            {
                "label": m.name,
                "url": reverse("map:detail", args=[club.slug, m.pk]),
                "icon": "map",
                "subtext": "View map",
            }
            for m in all_maps
        ]
        if not map_items:
            map_items.append({
                "label": "Map",
                "url": reverse("map:index", args=[club.slug]),
                "icon": "map",
                "subtext": "No maps yet",
            })
        
        # Build request URL for the first map with uncredited tiles
        request_url = None
        if first_map_data:
            hex_map, uncredited_tiles = first_map_data
            base_url = reverse("map:detail", args=[club.slug, hex_map.pk])
            # Pre-filter to this character's visits
            request_url = f"{base_url}?characters={character.pk}&view=mine"
        
        return {
            "maps": all_maps,
            "map_items": map_items,
            "maps_data": maps_data,
            "total_uncredited": total_uncredited,
            "request_url": request_url,
        }

    def should_show(self, request, club, character, membership):
        _, total_uncredited, _ = self._get_uncredited_data(club, character)
        return total_uncredited > 0


@dataclass
class MessagesProvider:
    """Message admins and unread count."""

    key: str = "messages"
    order: int = 6
    template: str = "accounts/_dashboard_messages.html"

    def get_context(self, request, club, character, membership):
        from accounts.models import Message

        unread_count = Message.objects.for_club(club).filter(
            status=Message.Status.OPEN
        ).exclude(sender=membership).count()

        message_items = [
            {
                "label": "Message Admins",
                "url": reverse("accounts:message_new", args=[club.slug]),
                "icon": "pencil",
                "subtext": "Send a message to club admins",
            },
        ]

        return {
            "unread_count": unread_count,
            "message_items": message_items,
        }

    def should_show(self, request, club, character, membership):
        return True


@dataclass
class PlayerShopProvider:
    """Player shop status (conditional)."""

    key: str = "player_shop"
    order: int = 7
    template: str = "accounts/_dashboard_player_shop.html"

    def get_context(self, request, club, character, membership):
        from player_characters.player_shop import listed_rows

        # Only show if character has shop_open = True
        if not character.shop_open:
            return {"shop_open": False}

        # Count listed items
        listed = listed_rows(character)
        listed_count = len(listed)

        # TODO: Add recent sales count when sales tracking is available
        recent_sales = 0

        return {
            "shop_open": True,
            "listed_count": listed_count,
            "recent_sales": recent_sales,
            "manage_url": reverse("shops:player_shop", args=[club.slug, character.pk]),
        }

    def should_show(self, request, club, character, membership):
        return character.shop_open


@dataclass
class ConsumablesProvider:
    """Quick consume for known consumable items (conditional)."""

    key: str = "consumables"
    order: int = 8
    template: str = "accounts/_dashboard_consumables.html"

    CONSUMABLE_KEYWORDS = (
        "potion",
        "scroll",
        "elixir",
        "antidote",
        "ration",
        "food",
        "water",
        "poison",
        "oil",
        "bomb",
        "grenade",
        "alchemy",
        "herb",
        "medicine",
        "remedy",
        "salve",
        "tonic",
        "draft",
        "draught",
        "vial",
        "flask",
    )

    def _is_consumable(self, item):
        """Check if item name suggests it's consumable."""
        name_lower = item.name.lower()
        return any(kw in name_lower for kw in self.CONSUMABLE_KEYWORDS)

    def get_context(self, request, club, character, membership):
        from items.models import Item
        from ledger.services import available_items

        have = available_items(character)
        if not have:
            return {"consumable_items": []}

        consumable_items = []
        for item_id, qty in have.items():
            if qty <= 0:
                continue
            item = Item.objects.filter(pk=item_id).first()
            if item and self._is_consumable(item):
                consumable_items.append({
                    "item": item,
                    "quantity": qty,
                    "consume_url": reverse(
                        "characters:player_consume",
                        args=[club.slug, character.pk, item.pk],
                    ),
                })

        return {"consumable_items": consumable_items}

    def should_show(self, request, club, character, membership):
        from items.models import Item
        from ledger.services import available_items

        have = available_items(character)
        if not have:
            return False
        for item_id, qty in have.items():
            if qty > 0:
                item = Item.objects.filter(pk=item_id).first()
                if item and self._is_consumable(item):
                    return True
        return False


# =============================================================================
# Dashboard Context Building (Refactored to Use Providers)
# =============================================================================


def _get_dashboard_context(request, club, character, membership):
    """Build the context dictionary for the player dashboard using providers."""
    providers = []
    for provider in get_providers():
        if provider.should_show(request, club, character, membership):
            ctx = provider.get_context(request, club, character, membership)
            providers.append({
                "key": provider.key,
                "order": provider.order,
                "template": provider.template,
                "ctx": ctx,
            })

    # Build header context
    coin_sum = coin_summary(character)
    downtime_balance = downtime_services.balance(character)
    junk = junk_rows(character)
    junk_val = junk_value(character, junk)

    trades_qs = club_queryset(request, Trade).filter(status__in=OPEN)
    my_trades = trades_qs.filter(
        Q(sender__owner=membership) | Q(receiver__owner=membership)
    ).select_related("sender__owner__user", "receiver__owner__user")

    open_trades_data = []
    for t in my_trades:
        if t.sender.owner_id == membership.id:
            other = t.receiver
            side = "sender"
        else:
            other = t.sender
            side = "receiver"
        open_trades_data.append({
            "trade": t,
            "other_character": other,
            "side": side,
            "status_display": t.get_status_display(),
        })

    from accounts.models import Message
    unread_count = Message.objects.for_club(club).filter(
        status=Message.Status.OPEN
    ).exclude(sender=membership).count()

    return {
        "character": character,
        "coin_summary": coin_sum,
        "downtime_balance": downtime_balance,
        "junk_count": len(junk),
        "junk_value": junk_val,
        "open_trades": open_trades_data,
        "unread_count": unread_count,
        "membership": membership,
        "dashboard_providers": providers,
    }


@club_member_required
def player_dashboard(request, club_slug):
    """Player dashboard with contextual quick actions for between-session tasks."""
    club = request.club
    membership = request.membership
    character = selected_character(request)

    # If user is GM or admin, redirect to club home (navigation cards)
    if is_game_master(request.user, club) or is_club_admin(request.user, club):
        from django.shortcuts import redirect
        return redirect("club_home", club_slug=club.slug)

    # If no character selected, show character selector prompt
    if character is None:
        return render(request, "accounts/dashboard_no_character.html", {
            "club": club,
            "membership": membership,
        })

    ctx = _get_dashboard_context(request, club, character, membership)
    return render(request, "accounts/dashboard.html", ctx)


# =============================================================================
# HTMX Partial Endpoints
# =============================================================================


@club_member_required
def dashboard_partial(request, club_slug, provider_key):
    """HTMX partial endpoint for a dashboard provider."""
    club = request.club
    membership = request.membership
    character = selected_character(request)

    if character is None:
        from django.http import Http404
        raise Http404("No character selected.")

    provider = get_provider(provider_key)
    if provider is None:
        from django.http import Http404
        raise Http404(f"Provider '{provider_key}' not found.")

    if not provider.should_show(request, club, character, membership):
        from django.http import Http404
        raise Http404(f"Provider '{provider_key}' not available.")

    ctx = provider.get_context(request, club, character, membership)
    html = render_to_string(provider.template, ctx, request=request)
    from django.http import HttpResponse
    return HttpResponse(html)


# =============================================================================
# Character Preview Endpoint
# =============================================================================


@club_member_required
def character_preview(request, club_slug, pk):
    """Character preview endpoint returning JSON for tooltip."""
    membership = request.membership

    from accounts.scoping import club_get_object_or_404
    from player_characters.models import Character
    character = club_get_object_or_404(request, Character, pk=pk)

    # Verify ownership
    if character.owner_id != membership.id:
        from django.http import Http404
        raise Http404("Not your character.")

    # Build preview data
    coin_sum = coin_summary(character)
    downtime_balance = downtime_services.balance(character)
    junk = junk_rows(character)
    junk_val = junk_value(character, junk)

    trades_qs = club_queryset(request, Trade).filter(status__in=OPEN)
    my_trades = trades_qs.filter(
        Q(sender__owner=membership) | Q(receiver__owner=membership)
    )
    open_trades_count = my_trades.count()

    return JsonResponse({
        "name": character.name,
        "level": character.level,
        "char_class": character.char_class,
        "species": character.species,
        "coins_available": coin_sum.available,
        "junk_count": len(junk),
        "junk_value": junk_val,
        "downtime_balance": downtime_balance,
        "open_trades_count": open_trades_count,
    })


@club_member_required
def print_session_pack_modal(request, club_slug, pk):
    """HTMX partial endpoint for the Print Session Pack options modal."""
    from accounts.scoping import club_get_object_or_404
    from player_characters.models import Character
    character = club_get_object_or_404(request, Character, pk=pk)

    # Verify ownership
    if character.owner_id != request.membership.id:
        from django.http import Http404
        raise Http404("Not your character.")

    return render(request, "accounts/_print_session_pack_modal.html", {
        "club": request.club,
        "character": character,
    })