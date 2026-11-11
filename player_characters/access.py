from django.core.exceptions import PermissionDenied

from accounts.permissions import can_view_inventory


def owns_character(user, character):
    """True only for the owning player. No superuser bypass."""
    return bool(user.is_authenticated and character.owner.user_id == user.id)


def can_edit_character(user, character):
    """Same people as the inventory viewers: owner, GM, club admin, site admin."""
    return can_view_inventory(user, character)


def require_inventory_access(user, character):
    if not can_view_inventory(user, character):
        raise PermissionDenied
