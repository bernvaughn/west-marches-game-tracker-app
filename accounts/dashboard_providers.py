"""Dashboard provider system for extensible dashboard widgets."""

from typing import Protocol

from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from downtime import services as downtime_services
from downtime.models import DowntimeAction
from items.magic_types import MagicType
from player_characters.junk import junk_rows
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


class DowntimeDashboardProvider:
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
            actions.append({
                "action": action,
                "cost": action.cost,
                "reason": reason,
                "affordable": not reason,
                "spend_url": reverse("accounts:dashboard_downtime_spend", args=[club.slug, action.pk]),
            })

        return {
            "downtime_balance": downtime_balance,
            "actions": actions,
        }

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        today = timezone.localdate()
        return DowntimeAction.objects.for_club(club).live_on(today).filter(entries__isnull=False).exists()


class QuickActionsProvider:
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