"""Dashboard provider system for extensible dashboard widgets."""

from abc import ABC
from typing import Protocol

from django.db.models import Count
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator

from accounts.models import Message
from downtime import services as downtime_services
from downtime.models import DowntimeAction
from items.magic_types import MagicType
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import available_items
from map.models import HexMap
from map.services import get_uncredited_tiles
from player_characters.junk import junk_rows
from player_characters.models import Trade
from player_characters.player_shop import listed_rows
from player_characters.trade_services import OPEN
from quests.models import Quest, QuestCompletion
from shops.models import ShopStock
from shops.services import open_shops


class DashboardProvider(Protocol):
    """Protocol for a dashboard widget/section provider."""

    key: str
    order: int
    template: str

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        """Return context for this provider's template."""
        ...

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        """Whether to render this provider for the current user."""
        return True


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


# =============================================================================
# Existing Providers (from original dashboard_providers.py)
# =============================================================================


class QuickActionsProvider(BaseDashboardProvider):
    """Provides 'Quick Actions' section: Sell Junk and Buy Potions buttons with HTMX modals."""

    key = "quick_actions"
    order = 1
    template = "accounts/_dashboard_quick_actions.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        has_junk = len(junk_rows(character)) > 0
        has_potions = self._has_healing_potions(club)
        return {
            "has_junk": has_junk,
            "has_potions": has_potions,
            "junk_count": len(junk_rows(character)) if has_junk else 0,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        ctx = self.get_context(request, club, character, membership)
        return ctx["has_junk"] or ctx["has_potions"]

    def _has_healing_potions(self, club) -> bool:
        """Check if any open shop has healing potions in stock."""
        today = timezone.localdate()
        open_shop_qs = open_shops(club, today)
        if not open_shop_qs.exists():
            return False
        return ShopStock.objects.filter(
            shop__in=open_shop_qs,
            item__magic_type=MagicType.POTION,
            quantity__gt=0,
        ).exists()


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
            spend_url = reverse(
                "accounts:dashboard_downtime_spend", args=[club.slug, action.pk]
            )
            actions.append({
                "action": action,
                "cost": action.cost,
                "reason": reason,
                "affordable": not reason,
                "spend_url": spend_url,
            })

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

    def _is_consumable(self, item: Item, quantity: int) -> bool:
        """Check if item is consumable based on quantity or traits."""
        if quantity > 1:
            return True
        if item.traits and "consumable" in item.traits.lower():
            return True
        return False

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        have = available_items(character)
        if not have:
            return {"consumable_items": []}

        consumable_items = []
        for item_id, qty in have.items():
            if qty <= 0:
                continue
            item = Item.objects.filter(pk=item_id).first()
            if item and self._is_consumable(item, qty):
                consumable_items.append({
                    "item": item,
                    "quantity": qty,
                    "consume_partial_url": reverse(
                        "accounts:consumable_consume_partial",
                        args=[club.slug, item.pk],
                    ),
                })

        return {"consumable_items": consumable_items}

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        have = available_items(character)
        if not have:
            return False
        for item_id, qty in have.items():
            if qty > 0:
                item = Item.objects.filter(pk=item_id).first()
                if item and self._is_consumable(item, qty):
                    return True
        return False


# =============================================================================
# Providers migrated from dashboard.py
# =============================================================================


class TradesDashboardProvider(BaseDashboardProvider):
    """Open trades with status badges and Act Now buttons."""

    key = "trades"
    order = 2
    template = "accounts/_dashboard_trades.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        from django.db.models import Q

        from accounts.scoping import club_queryset
        from player_characters.trade_status_line import trade_status_line

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

            # Get U78 status wording
            status_text = trade_status_line(t, side)

            # Determine Act Now button
            action_url = None
            action_label = None
            action_method = "get"

            if t.status == Trade.Status.REQUESTED:
                if side == "receiver":
                    action_label = "Accept"
                    action_url = reverse("trades:accept", args=[club.slug, t.pk])
                    action_method = "post"
                else:  # sender
                    action_label = "Cancel"
                    action_url = reverse("trades:cancel", args=[club.slug, t.pk])
                    action_method = "post"
            elif t.status == Trade.Status.ACCEPTED:
                approved = {"sender": t.sender_approved, "receiver": t.receiver_approved}
                if not approved[side]:
                    # Viewer has not approved yet
                    action_label = "Change"
                    action_url = reverse("trades:edit_side", args=[club.slug, t.pk])
                    action_method = "get"
                elif approved[side] and not approved["receiver" if side == "sender" else "sender"]:
                    # Viewer approved, other hasn't
                    action_label = "Approve"
                    action_url = reverse("trades:approve", args=[club.slug, t.pk])
                    action_method = "post"
                # else both approved -> trade completes, no action

            open_trades_data.append({
                "trade": t,
                "other_character": other,
                "side": side,
                "status_text": status_text,
                "action_url": action_url,
                "action_label": action_label,
                "action_method": action_method,
            })

        return {
            "open_trades_data": open_trades_data,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        from django.db.models import Q

        from accounts.scoping import club_queryset

        trades_qs = club_queryset(request, Trade).filter(status__in=OPEN)
        return trades_qs.filter(
            Q(sender__owner=membership) | Q(receiver__owner=membership)
        ).exists()


class QuestsDashboardProvider(BaseDashboardProvider):
    """Ready-to-turn-in quests."""

    key = "quests"
    order = 3
    template = "accounts/_dashboard_quests.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
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

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        return True


class MessagesDashboardProvider(BaseDashboardProvider):
    """Message admins and unread count (for admin messages)."""

    key = "messages"
    order = 6
    template = "accounts/_dashboard_messages.html"

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
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

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        return True


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
            map_items.append({
                "label": "Map",
                "url": reverse("map:index", args=[club.slug]),
                "icon": "map",
                "subtext": "No maps yet",
            })
        
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
        from accounts.models import Message
        from accounts.scoping import club_queryset

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

            message_rows.append({
                "message": msg,
                "subject": subject,
                "sent_date": msg.created,
                "status": msg.status,
                "status_display": msg.get_status_display(),
                "status_badge_class": status_badge_class,
                "admin_note_preview": admin_note_preview,
                "detail_url": reverse("accounts:message_detail", args=[club.slug, msg.pk]),
            })

        return {
            "message_rows": message_rows,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        from accounts.models import Message
        from accounts.scoping import club_queryset
        return (
            club_queryset(request, Message)
            .filter(sender=membership)
            .exists()
        )

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


# For backward compatibility with existing imports
PlayerShopProvider = PlayerShopDashboardProvider


# =============================================================================
# Registration System
# =============================================================================

_providers: dict[str, DashboardProvider] = {}


def register_provider(provider: DashboardProvider) -> None:
    """Register a dashboard provider."""
    _providers[provider.key] = provider


def get_providers() -> list[DashboardProvider]:
    """Get all registered providers sorted by order."""
    return sorted(_providers.values(), key=lambda p: p.order)


def get_provider(key: str) -> DashboardProvider | None:
    """Get a specific provider by key."""
    return _providers.get(key)