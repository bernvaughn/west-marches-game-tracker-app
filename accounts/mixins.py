"""Reusable view mixins to eliminate repeated boilerplate across apps."""

from accounts.permissions import (
    can_view_inventory as _can_view_inventory,
)
from accounts.permissions import (
    is_club_admin as _is_club_admin,
)
from accounts.permissions import (
    is_game_master as _is_game_master,
)
from accounts.scoping import club_get_object_or_404 as _club_get_object_or_404
from accounts.scoping import club_queryset as _club_queryset
from downtime import services as downtime_services
from player_characters.inventory import coin_summary, inventory_rows
from player_characters.junk import junk_rows, junk_value
from player_characters.selection import selected_character


class ClubScopedMixin:
    """Mixin providing club-scoped query helpers."""

    def get_club_queryset(self, model):
        """Return a queryset filtered to the current club."""
        return _club_queryset(self.request, model)

    def get_club_object_or_404(self, model, **kwargs):
        """Return a club-scoped object or raise Http404."""
        return _club_get_object_or_404(self.request, model, **kwargs)


class CharacterContextMixin:
    """Mixin providing character context building helpers."""

    def get_character_context(self, character):
        """
        Build a context dictionary for a character.

        Returns dict with:
        - inventory_rows: list of InventoryRow
        - coin_summary: CoinSummary
        - junk_rows: list of JunkRow
        - junk_value: int (total value in CP)
        - downtime_balance: int (downtime points balance)
        """
        if character is None:
            return {
                "inventory_rows": [],
                "coin_summary": None,
                "junk_rows": [],
                "junk_value": 0,
                "downtime_balance": 0,
            }

        rows = inventory_rows(character)
        junk = junk_rows(character)

        return {
            "inventory_rows": rows,
            "coin_summary": coin_summary(character),
            "junk_rows": junk,
            "junk_value": junk_value(character, junk),
            "downtime_balance": downtime_services.balance(character),
        }

    def get_selected_character(self):
        """Return the selected character for the current request."""
        return selected_character(self.request)


class PermissionMixin:
    """Mixin providing permission check helpers."""

    def is_club_admin(self, user, club):
        """Check if user is a club admin (or superuser)."""
        return _is_club_admin(user, club)

    def is_game_master(self, user, club):
        """Check if user is a game master (or superuser)."""
        return _is_game_master(user, club)

    def can_view_inventory(self, user, character):
        """Check if user can view the character's inventory."""
        return _can_view_inventory(user, character)


class ClubContextMixin:
    """Mixin providing club context helpers."""

    @property
    def club(self):
        """Return the current club from the request."""
        return self.request.club

    @property
    def membership(self):
        """Return the current membership from the request."""
        return self.request.membership

    @property
    def user(self):
        """Return the current user from the request."""
        return self.request.user


class ViewMixin(ClubScopedMixin, CharacterContextMixin, PermissionMixin, ClubContextMixin):
    """Combined mixin with all common view functionality."""

    pass
