"""Player Shop dashboard provider."""

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from accounts.scoping import club_queryset
from ledger.models import LedgerEntry
from player_characters.player_shop import listed_rows


@dataclass
class PlayerShopDashboardProvider:
    """Player shop status (conditional)."""

    key: str = "player_shop"
    order: int = 7
    template: str = "accounts/_dashboard_player_shop.html"

    def get_context(self, request, club, character, membership):
        # Only show if character has shop_open = True
        if not character.shop_open:
            return {"shop_open": False}

        # Count listed items
        listed = listed_rows(character)
        listed_count = len(listed)

        # Count today's sales (player_shop ledger entries where character is the seller)
        today = timezone.localdate()
        recent_sales = (
            club_queryset(request, LedgerEntry)
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

    def should_show(self, request, club, character, membership):
        return character.shop_open


# For backward compatibility with existing imports
PlayerShopProvider = PlayerShopDashboardProvider