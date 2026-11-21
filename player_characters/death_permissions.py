"""Permission helpers for character death and undo actions.

These are separate from life.py (C1 owns life.py) and from views/characters.py
(C7 owns views/characters.py). They are exposed to templates via
templatetags/death_tags.py.
"""

from datetime import timedelta

from django.utils import timezone

from accounts.permissions import can_see_gm_details
from player_characters.access import owns_character
from player_characters.models import CharacterStatusChange


def can_mark_dead(user, character):
    """Return True if user can mark this character as dead.

    Owner, GM, club admin, or site admin.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if owns_character(user, character):
        return True
    return can_see_gm_details(user, character.club)


def can_undo_death(user, character):
    """Return True if user can undo this character's death.

    - GM, club admin, site admin: always (if character is dead).
    - Owner: only if the newest DIED entry was made by the owner within 24 hours.
    """
    if not character.is_dead:
        return False

    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    club = character.club
    # GM or club admin
    if can_see_gm_details(user, club):
        return True

    # Owner check
    if not owns_character(user, character):
        return False

    # Check if the newest DIED entry was made by this owner within 24 hours
    owner_membership = character.owner
    latest_died = (
        CharacterStatusChange.objects.filter(
            character=character,
            kind=CharacterStatusChange.Kind.DIED,
        )
        .order_by("-at", "-id")
        .first()
    )

    if latest_died is None or latest_died.by_id != owner_membership.id:
        return False

    # Within 24 hours
    return (timezone.now() - latest_died.at) < timedelta(hours=24)
