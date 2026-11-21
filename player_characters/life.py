"""Central guards and services for character death and archive state.

All buy/downtime/quest/claim call these. They check state only.
Permissions (owner/GM/admin/24-hour undo) live in the views.
"""

from django.db import transaction
from django.utils import timezone


class LifeError(Exception):
    """Raised when a character cannot act due to death/archive state."""

    pass


def buy_block_reason(character):
    """Return a user-facing reason text why the character cannot buy, or '' if allowed."""
    if character is None:
        return ""
    if character.is_archived:
        return f"{character.name} is archived"
    if character.is_dead:
        return f"{character.name} died on {character.died_on.isoformat()}"
    return ""


def sell_block_reason(character):
    """Return a user-facing reason text why the character cannot sell, or '' if allowed."""
    if character is None:
        return ""
    if character.is_archived:
        return f"{character.name} is archived"
    return ""


def can_buy(character):
    """Can this character buy? Living and not archived."""
    return character is not None and not character.is_dead and not character.is_archived


def can_sell(character):
    """Can this character sell? Not archived (dead is allowed)."""
    return character is not None and not character.is_archived


def can_act(character):
    """Can this character act (buy/downtime/quest/claim)? Same as can_buy."""
    return can_buy(character)


def act_block_reason(character):
    """Reason text for why the character cannot act. Same as buy_block_reason."""
    return buy_block_reason(character)


def require_can_buy(character):
    """Raise LifeError if the character cannot buy."""
    reason = buy_block_reason(character)
    if reason:
        raise LifeError(reason)


def require_can_sell(character):
    """Raise LifeError if the character cannot sell."""
    reason = sell_block_reason(character)
    if reason:
        raise LifeError(reason)


def require_can_act(character):
    """Raise LifeError if the character cannot act."""
    reason = act_block_reason(character)
    if reason:
        raise LifeError(reason)


# --- Service functions ---


def mark_dead(character, *, by, died_on=None, note=""):
    """Mark a character as dead. Returns the new CharacterStatusChange row."""
    if character.is_dead:
        raise LifeError(f"{character.name} is already dead")
    if died_on is None:
        died_on = timezone.localdate()
    if died_on > timezone.localdate():
        raise LifeError("Death date cannot be in the future")

    with transaction.atomic():
        character = Character.objects.select_for_update().get(pk=character.pk)
        if character.is_dead:
            raise LifeError(f"{character.name} is already dead")
        character.died_on = died_on
        character.death_note = note
        character.save(update_fields=["died_on", "death_note"])

        history = CharacterStatusChange.objects.create(
            character=character,
            kind=CharacterStatusChange.Kind.DIED,
            by=by,
            at=timezone.now(),
            note=note,
            date=died_on,
        )
    return history


def undo_death(character, *, by, note=""):
    """Undo a character's death. Returns the new CharacterStatusChange row."""
    if not character.is_dead:
        raise LifeError(f"{character.name} is not dead")

    with transaction.atomic():
        character = Character.objects.select_for_update().get(pk=character.pk)
        if not character.is_dead:
            raise LifeError(f"{character.name} is not dead")
        character.died_on = None
        character.death_note = ""
        character.save(update_fields=["died_on", "death_note"])

        history = CharacterStatusChange.objects.create(
            character=character,
            kind=CharacterStatusChange.Kind.REVIVED,
            by=by,
            at=timezone.now(),
            note=note,
            date=timezone.localdate(),
        )
    return history


def archive(character, *, by, note=""):
    """Archive a character. Closes their stall. Returns the new CharacterStatusChange row."""
    if character.is_archived:
        raise LifeError(f"{character.name} is already archived")

    with transaction.atomic():
        character = Character.objects.select_for_update().get(pk=character.pk)
        if character.is_archived:
            raise LifeError(f"{character.name} is already archived")
        character.archived_at = timezone.now()
        character.shop_open = False
        character.save(update_fields=["archived_at", "shop_open"])

        history = CharacterStatusChange.objects.create(
            character=character,
            kind=CharacterStatusChange.Kind.ARCHIVED,
            by=by,
            at=timezone.now(),
            note=note,
            date=timezone.localdate(),
        )
    return history


def unarchive(character, *, by, note=""):
    """Unarchive a character. Does not reopen the stall.
    Returns the new CharacterStatusChange row."""
    if not character.is_archived:
        raise LifeError(f"{character.name} is not archived")

    with transaction.atomic():
        character = Character.objects.select_for_update().get(pk=character.pk)
        if not character.is_archived:
            raise LifeError(f"{character.name} is not archived")
        character.archived_at = None
        character.save(update_fields=["archived_at"])

        history = CharacterStatusChange.objects.create(
            character=character,
            kind=CharacterStatusChange.Kind.UNARCHIVED,
            by=by,
            at=timezone.now(),
            note=note,
            date=timezone.localdate(),
        )
    return history


# Import at bottom to avoid circular imports
from player_characters.models import Character, CharacterStatusChange  # noqa: E402
