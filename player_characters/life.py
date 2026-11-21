"""Central guards and services for character death and archive state.

All buy/downtime/quest/claim call these. They check state only.
Permissions (owner/GM/admin/24-hour undo) live in the views.
"""

from django.db import transaction
from django.utils import timezone

from player_characters.models import Character, CharacterStatusChange


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


def _apply(character, *, kind, by, note, date, _check, **changes):
    """Apply `changes` to the locked row, write one history row, refresh `character`.

    The caller's instance is updated in place, so it is current after the call.
    """
    with transaction.atomic():
        locked = Character.objects.select_for_update().get(pk=character.pk)
        _check(locked)
        for field, value in changes.items():
            setattr(locked, field, value)
        locked.save(update_fields=list(changes))
        history = CharacterStatusChange.objects.create(
            character=locked,
            kind=kind,
            by=by,
            at=timezone.now(),
            note=note,
            date=date,
        )
    for field in changes:
        setattr(character, field, getattr(locked, field))
    return history


def mark_dead(character, *, by, died_on=None, note=""):
    """Mark a character as dead. Returns the new CharacterStatusChange row."""
    if died_on is None:
        died_on = timezone.localdate()
    if died_on > timezone.localdate():
        raise LifeError("Death date cannot be in the future")

    def check(c):
        if c.is_dead:
            raise LifeError(f"{c.name} is already dead")

    return _apply(
        character,
        kind=CharacterStatusChange.Kind.DIED,
        by=by,
        note=note,
        date=died_on,
        _check=check,
        died_on=died_on,
        death_note=note,
    )


def undo_death(character, *, by, note=""):
    """Undo a character's death. Returns the new CharacterStatusChange row."""

    def check(c):
        if not c.is_dead:
            raise LifeError(f"{c.name} is not dead")

    return _apply(
        character,
        kind=CharacterStatusChange.Kind.REVIVED,
        by=by,
        note=note,
        date=timezone.localdate(),
        _check=check,
        died_on=None,
        death_note="",
    )


def archive(character, *, by, note=""):
    """Archive a character. Closes their stall. Returns the new CharacterStatusChange row."""

    def check(c):
        if c.is_archived:
            raise LifeError(f"{c.name} is already archived")

    return _apply(
        character,
        kind=CharacterStatusChange.Kind.ARCHIVED,
        by=by,
        note=note,
        date=timezone.localdate(),
        _check=check,
        archived_at=timezone.now(),
        shop_open=False,
    )


def unarchive(character, *, by, note=""):
    """Unarchive a character. Does not reopen the stall.

    Returns the new CharacterStatusChange row.
    """

    def check(c):
        if not c.is_archived:
            raise LifeError(f"{c.name} is not archived")

    return _apply(
        character,
        kind=CharacterStatusChange.Kind.UNARCHIVED,
        by=by,
        note=note,
        date=timezone.localdate(),
        _check=check,
        archived_at=None,
    )
