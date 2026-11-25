"""Services for player-written items: add, edit, remove.

Every change writes an append-only ``PlayerItemChange`` history row.
Player-written items are unsellable by construction: they are not
catalogue items, so shops, stalls, quests and rewards never see them.
"""

from django.core.exceptions import ValidationError

from player_items.models import MAX_ITEMS_PER_CHARACTER, PlayerItem, PlayerItemChange
from player_items.rules import character_can_change_items


def _require_can_change(character):
    if not character_can_change_items(character):
        msg = "This character cannot change items."
        raise ValidationError(msg)


def add_player_item(club, character, name, quantity, note, by):
    """Add a player-written item to a character's sheet.

    Enforces the 50-item limit per character and writes an ADDED
    history row.
    """
    _require_can_change(character)
    count = PlayerItem.objects.for_club(club).filter(character=character).count()
    if count >= MAX_ITEMS_PER_CHARACTER:
        msg = f"Cannot have more than {MAX_ITEMS_PER_CHARACTER} player-written items per character."
        raise ValidationError(msg)
    item = PlayerItem.objects.create(
        club=club,
        character=character,
        name=name,
        quantity=quantity,
        note=note or "",
    )
    PlayerItemChange.objects.create(
        club=club,
        character=character,
        kind=PlayerItemChange.Kind.ADDED,
        new_name=name,
        quantity=quantity,
        by=by,
    )
    return item


def edit_player_item(player_item, name, quantity, note, by):
    """Edit a player-written item and write an EDITED history row."""
    character = player_item.character
    club = player_item.club
    _require_can_change(character)
    old_name = player_item.name
    player_item.name = name
    player_item.quantity = quantity
    player_item.note = note or ""
    player_item.save()
    PlayerItemChange.objects.create(
        club=club,
        character=character,
        kind=PlayerItemChange.Kind.EDITED,
        old_name=old_name,
        new_name=name,
        quantity=quantity,
        by=by,
    )
    return player_item


def remove_player_item(player_item, by):
    """Remove a player-written item and write a REMOVED history row."""
    character = player_item.character
    club = player_item.club
    _require_can_change(character)
    name = player_item.name
    quantity = player_item.quantity
    player_item.delete()
    PlayerItemChange.objects.create(
        club=club,
        character=character,
        kind=PlayerItemChange.Kind.REMOVED,
        old_name=name,
        quantity=quantity,
        by=by,
    )
