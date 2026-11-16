"""Dashboard context providers for extensible dashboard sections."""

from typing import Protocol

from django.utils import timezone

from items.magic_types import MagicType
from player_characters.junk import junk_rows
from shops.models import ShopStock
from shops.services import open_shops


class DashboardProvider(Protocol):
    """Protocol for a dashboard widget/section provider."""

    key: str
    order: int
    template: str

    def get_context(self, request, club, character, membership) -> dict:
        """Return context for this provider's template."""
        ...

    def should_show(self, request, club, character, membership) -> bool:
        """Whether to render this provider for the current user."""
        return True


class QuickActionsProvider:
    """Provides 'Quick Actions' section: Sell Junk and Buy Potions buttons."""

    key = "quick_actions"
    order = 1
    template = "accounts/_dashboard_quick_actions.html"

    def get_context(self, request, club, character, membership) -> dict:
        has_junk = len(junk_rows(character)) > 0
        has_potions = self._has_healing_potions(club)
        return {
            "has_junk": has_junk,
            "has_potions": has_potions,
        }

    def should_show(self, request, club, character, membership) -> bool:
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


# Registry for dashboard providers
_dashboard_providers: list[DashboardProvider] = []


def register_provider(provider: DashboardProvider) -> None:
    """Register a dashboard provider."""
    _dashboard_providers.append(provider)


def get_providers() -> list[DashboardProvider]:
    """Get all registered providers sorted by order."""
    return sorted(_dashboard_providers, key=lambda p: p.order)