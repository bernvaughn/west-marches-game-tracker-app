"""Dashboard provider system for extensible dashboard widgets."""

from abc import ABC
from typing import TYPE_CHECKING

from django.db.models import Count, QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator

from accounts.models import Message
from accounts.scoping import club_queryset
from downtime import services as downtime_services
from downtime.models import DowntimeAction
from items.magic_types import MagicType
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import available_items
from map.models import HexMap
from map.services import get_uncredited_tiles
from player_characters.inventory import coin_summary
from player_characters.junk import junk_rows, junk_value
from player_characters.player_shop import listed_rows
from quests.models import Quest, QuestCompletion
from shops.models import ShopStock
from shops.services import open_shops

if TYPE_CHECKING:
    from clubs.models import Club

    from player_characters.models import Character


def is_consumable(item: Item) -> bool:
    """Check if item is consumable.

    An item is consumable when its magic type is Potion or Scroll, or when its
    traits contain the word "consumable" (case-insensitive). Quantity never
    decides.
    """
    if item.magic_type in (MagicType.POTION, MagicType.SCROLL):
        return True
    traits = item.traits or ""
    return "consumable" in traits.lower()


def get_healing_potion_stock(club: "Club", today) -> QuerySet[ShopStock]:
    """Return queryset of healing potion stocks from open shops with quantity > 0."""
    open_shop_qs = open_shops(club, today)
    if not open_shop_qs.exists():
        return ShopStock.objects.none()
    return (
        ShopStock.objects.filter(
            shop__in=open_shop_qs,
            item__magic_type=MagicType.POTION,
            quantity__gt=0,
        )
        .select_related("shop", "item")
        .order_by("shop__street_position", "shop__name", "item__name")
    )


def build_header_stats(character: "Character") -> dict:
    """Build header stats dict: coins, downtime, junk count/value, unread messages."""
    coin_sum = coin_summary(character)
    downtime_balance = downtime_services.balance(character)
    junk = junk_rows(character)
    junk_val = junk_value(character, junk)

    return {
        "coin_summary": coin_sum,
        "downtime_balance": downtime_balance,
        "junk_count": len(junk),
        "junk_value": junk_val,
    }


class BaseDashboardProvider(ABC):
    """Base class for dashboard providers with common utilities."""

    key: str
    order: int
    template: str

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        """Return context for this provider's template. Must be implemented by subclasses."""
        raise NotImplementedError

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        """Whether to render this provider for the current user. Default: always show."""
        return True


class HeaderDashboardProvider(BaseDashboardProvider):
    """Dashboard header stats: coins, downtime, junk count/value, messages."""

    key = "header"
    order = 0
    template = "accounts/_dashboard_header.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        return build_header_stats(character)


# =============================================================================
# Existing Providers (from original dashboard_providers.py)
# =============================================================================


class QuickActionsProvider(BaseDashboardProvider):
    """Provides 'Quick Actions' section: Sell Junk and Buy Potions buttons with HTMX modals."""

    key = "quick_actions"
    order = 1
    template = "accounts/_dashboard_quick_actions.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        today = timezone.localdate()
        has_junk = len(junk_rows(character)) > 0
        has_potions = get_healing_potion_stock(club, today).exists()
        return {
            "has_junk": has_junk,
            "has_potions": has_potions,
            "junk_count": len(junk_rows(character)) if has_junk else 0,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        # Always show so the partial endpoint returns 200 even when empty,
        # allowing HTMX refresh to work after the last junk sale.
        return True


class DowntimeDashboardProvider(BaseDashboardProvider):
    """Provides 'Downtime' section with spend buttons for available actions."""

    key = "downtime"
    order = 4
    template = "accounts/_dashboard_downtime.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        today = timezone.localdate()
        downtime_balance = downtime_services.balance(character)

        live_actions = (
            DowntimeAction.objects.for_club(club)
            .live_on(today)
            .filter(entries__isnull=False)
            .distinct()
            .prefetch_related("entries__items__item")
        )

        actions = []
        for action in live_actions:
            reason = ""
            if downtime_balance < action.cost:
                reason = "Not enough downtime points."
            spend_url = reverse("accounts:dashboard_downtime_spend", args=[club.slug, action.pk])
            actions.append(
                {
                    "action": action,
                    "cost": action.cost,
                    "reason": reason,
                    "affordable": not reason,
                    "spend_url": spend_url,
                }
            )

        return {
            "downtime_balance": downtime_balance,
            "actions": actions,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        today = timezone.localdate()
        live_actions = DowntimeAction.objects.for_club(club).live_on(today)
        return live_actions.filter(entries__isnull=False).exists()


class ConsumablesDashboardProvider(BaseDashboardProvider):
    """Provides 'Consumables' section with 'Use 1' buttons for consumable items."""

    key = "consumables"
    order = 8
    template = "accounts/_dashboard_consumables.html"

    def _consumable_rows(self, character) -> list[tuple[Item, int]]:
        """Return list of (item, quantity) for consumable items the character has.

        Loads all items in a single query and filters to consumables.
        Preserves the iteration order of available_items.
        """
        have = available_items(character)
        if not have:
            return []

        # Filter to items with qty > 0 and collect their pks
        item_ids = [item_id for item_id, qty in have.items() if qty > 0]
        if not item_ids:
            return []

        # Single query to load all items
        items = Item.objects.filter(pk__in=item_ids)
        item_map = {item.pk: item for item in items}

        # Build result preserving order of have
        rows = []
        for item_id, qty in have.items():
            if qty <= 0:
                continue
            item = item_map.get(item_id)
            if item and is_consumable(item):
                rows.append((item, qty))
        return rows

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        rows = self._consumable_rows(character)
        consumable_items = [
            {
                "item": item,
                "quantity": qty,
                "consume_partial_url": reverse(
                    "accounts:consumable_consume_partial",
                    args=[club.slug, item.pk],
                ),
            }
            for item, qty in rows
        ]
        return {"consumable_items": consumable_items}

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        return bool(self._consumable_rows(character))


# =============================================================================
# Providers migrated from dashboard.py
# =============================================================================


class QuestsDashboardProvider(BaseDashboardProvider):
    """Ready-to-turn-in quests."""

    key = "quests"
    order = 3
    template = "accounts/_dashboard_quests.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        today = timezone.localdate()

        quests_qs = (
            Quest.objects.for_club(club)
            .prefetch_related("requirements__item", "rewards__item")
            .annotate(done=Count("completions"))
        )

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
            quest_items.append(
                {
                    "label": q.name,
                    "url": reverse("quests:detail", args=[club.slug, q.pk]),
                    "icon": "check-circle",
                    "subtext": "Ready to turn in",
                }
            )
        if not quest_items:
            quest_items.append(
                {
                    "label": "Quest Board",
                    "url": reverse("quests:index", args=[club.slug]),
                    "icon": "journal-text",
                    "subtext": "Browse available quests",
                }
            )

        return {
            "ready_quests": ready_quests,
            "quest_items": quest_items,
        }


class MessagesDashboardProvider(BaseDashboardProvider):
    """Message admins and unread count (for admin messages)."""

    key = "messages"
    order = 6
    template = "accounts/_dashboard_messages.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        message_items = [
            {
                "label": "Message Admins",
                "url": reverse("accounts:message_new", args=[club.slug]),
                "icon": "pencil",
                "subtext": "Send a message to club admins",
            },
        ]

        return {
            "message_items": message_items,
        }


class MapDashboardProvider(BaseDashboardProvider):
    """Map section with Request Map Credit shortcut for uncredited visits."""

    key = "map"
    order = 5
    template = "accounts/_dashboard_map.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        result = get_uncredited_tiles(club, character)

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
            map_items.append(
                {
                    "label": "Map",
                    "url": reverse("map:index", args=[club.slug]),
                    "icon": "map",
                    "subtext": "No maps yet",
                }
            )

        # Build request URL for the first map with uncredited tiles
        request_url = None
        if result.first_map:
            base_url = reverse("map:detail", args=[club.slug, result.first_map.pk])
            # Pre-filter to this character's visits
            request_url = f"{base_url}?characters={character.pk}&view=mine"

        return {
            "maps": all_maps,
            "map_items": map_items,
            "maps_data": result.maps_data,
            "total_uncredited": result.total_uncredited,
            "request_url": request_url,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        result = get_uncredited_tiles(club, character)
        return result.total_uncredited > 0


# =============================================================================
# Providers migrated from dashboard_messages.py
# =============================================================================


class MyMessagesDashboardProvider(BaseDashboardProvider):
    """Dashboard widget showing player's sent messages with status."""

    key = "my_messages"
    order = 7
    template = "accounts/_dashboard_my_messages.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        messages = (
            club_queryset(request, Message)
            .filter(sender=membership)
            .select_related("character")
            .order_by("-created")[:20]
        )

        message_rows = []
        for msg in messages:
            # Subject: first 50 chars of body or "Message to Admins"
            subject = Truncator(msg.body).chars(50)
            if not subject:
                subject = "Message to Admins"

            # Status badge
            status_badge_class = self._get_status_badge_class(msg.status)

            # Admin note preview (if handled/closed)
            admin_note_preview = None
            if msg.status in (Message.Status.HANDLED, Message.Status.CLOSED):
                admin_note_preview = self._get_admin_note_preview(msg)

            message_rows.append(
                {
                    "message": msg,
                    "subject": subject,
                    "sent_date": msg.created,
                    "status": msg.status,
                    "status_display": msg.get_status_display(),
                    "status_badge_class": status_badge_class,
                    "admin_note_preview": admin_note_preview,
                    "detail_url": reverse("accounts:message_detail", args=[club.slug, msg.pk]),
                }
            )

        return {
            "message_rows": message_rows,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        return club_queryset(request, Message).filter(sender=membership).exists()

    def _get_status_badge_class(self, status):
        """Return Bootstrap badge class for message status."""
        if status == Message.Status.OPEN:
            return "text-bg-warning"
        elif status == Message.Status.HANDLED:
            return "text-bg-success"
        elif status == Message.Status.CLOSED:
            return "text-bg-secondary"
        return "text-bg-light"

    def _get_admin_note_preview(self, message):
        """Get a preview of admin response from the message."""
        # Check if there are granted entries (admin responses)
        if message.granted_entries.exists():
            return "Admin response: items/coins granted"
        if message.granted_visits.exists():
            return "Admin response: map visit granted"
        if message.granted_credits.exists():
            return "Admin response: map credit granted"
        if message.granted_found_marks.exists():
            return "Admin response: map discovery granted"
        return "Admin handled this message"


# =============================================================================
# Providers migrated from dashboard_shop.py
# =============================================================================


class PlayerShopDashboardProvider(BaseDashboardProvider):
    """Player shop status (conditional)."""

    key = "player_shop"
    order = 7
    template = "accounts/_dashboard_player_shop.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        # Only show if character has shop_open = True
        if not character.shop_open:
            return {"shop_open": False}

        # Count listed items
        listed = listed_rows(character)
        listed_count = len(listed)

        # Count today's sales (player_shop ledger entries where character is the seller)
        today = timezone.localdate()
        recent_sales = (
            LedgerEntry.objects.for_club(club)
            .filter(
                character=character,
                kind=LedgerEntry.Kind.PLAYER_SHOP,
                date=today,
            )
            .count()
        )

        # Manage link goes to character detail (where shop toggle lives)
        manage_url = reverse("characters:detail", args=[club.slug, character.pk])

        return {
            "shop_open": True,
            "listed_count": listed_count,
            "recent_sales": recent_sales,
            "manage_url": manage_url,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        return character.shop_open


# =============================================================================
# New contextual action card providers (Story: Enhanced Dashboard)
# =============================================================================


# =============================================================================
# Registration System
# =============================================================================

_providers: dict[str, BaseDashboardProvider] = {}


def register_provider(provider: BaseDashboardProvider) -> None:
    """Register a dashboard provider."""
    _providers[provider.key] = provider


def get_providers() -> list[BaseDashboardProvider]:
    """Get all registered providers sorted by order."""
    return sorted(_providers.values(), key=lambda p: p.order)


def get_provider(key: str) -> BaseDashboardProvider | None:
    """Get a specific provider by key."""
    return _providers.get(key)
