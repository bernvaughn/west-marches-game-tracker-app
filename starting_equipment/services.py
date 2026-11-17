"""Services for starting equipment application."""

from typing import TYPE_CHECKING

from django.db.models import Q

from core.services import BaseService, ClubScopedService
from ledger.models import LedgerEntry
from ledger.services import LedgerLine, ledger

if TYPE_CHECKING:
    from accounts.models import Club, User
    from items.models import Item
    from ledger.models import LedgerEntry
    from player_characters.models import Character
    from starting_equipment.models import (
        MagicItemStartingOption,
        StartingEquipmentBackgroundEntry,
        StartingEquipmentBackgroundLine,
        StartingEquipmentClassEntry,
        StartingEquipmentClassLine,
        StartingEquipmentLevelCoins,
        StartingEquipmentTemplate,
        StartingEquipmentRequest,
    )


class StartingEquipmentError(Exception):
    """Base exception for starting equipment service errors."""


def apply_starting_equipment(
    character: "Character",
    template: "StartingEquipmentTemplate",
    actor: "User | None",
) -> "LedgerEntry | None":
    """
    Apply starting equipment for a new character.

    Creates one ledger entry with all granted items and coins.
    Returns None if no starting equipment was applied.

    Args:
        character: The new character to grant equipment to.
        template: The starting equipment template to use.
        actor: The user performing the grant (can be None).

    Returns:
        LedgerEntry if equipment was granted, None otherwise.
    """
    # Ensure template's club matches character's club
    if template.club_id != character.club_id:
        return None

    lines: list[LedgerLine] = []
    total_coins = 0

    # 1. Class equipment - match case-insensitively
    character_level = character.level or 1
    class_entry = (
        template.class_entries.filter(
            char_class__iexact=character.char_class,
        )
        .filter(
            Q(min_level__lte=character_level)
            & Q(max_level__gte=character_level),
        )
        .first()
    )

    if class_entry:
        # Add class coins
        total_coins += class_entry.coins_cp

        # Add class lines (skip choice groups)
        for line in class_entry.lines.filter(is_choice=False).select_related("item"):
            lines.append(
                LedgerLine(
                    item=line.item,
                    quantity=line.quantity,
                    coins=0,
                )
            )

    # 2. Background equipment - only if character has background set
    if character.background:
        bg_entry = (
            template.background_entries.filter(
                background__iexact=character.background,
            )
            .first()
        )

        if bg_entry:
            # Add background coins
            total_coins += bg_entry.coins_cp

            # Add background lines (skip choice groups)
            for line in bg_entry.lines.filter(is_choice=False).select_related("item"):
                lines.append(
                    LedgerLine(
                        item=line.item,
                        quantity=line.quantity,
                        coins=0,
                    )
                )

    # 3. Level coins for level > 1
    if character_level > 1:
        level_coins_entry = template.level_coins.filter(
            level=character_level,
        ).first()

        if level_coins_entry:
            total_coins += level_coins_entry.coins_cp

    # 4. Magic item requests - only approved ones
    for request in (
        character.starting_requests.filter(
            status=StartingEquipmentRequest.Status.APPROVED,
        )
        .select_related("item")
    ):
        # Check if item is in the template's magic options
        magic_option = (
            template.magic_options.filter(
                item=request.item,
            )
            .first()
        )
        if magic_option:
            for _ in range(request.quantity):
                lines.append(
                    LedgerLine(
                        item=request.item,
                        quantity=1,
                        coins=0,
                    )
                )

    # If nothing to grant, return None
    if not lines and total_coins == 0:
        return None

    # Create the ledger entry
    entry_lines = lines.copy()
    if total_coins > 0:
        entry_lines.append(LedgerLine(item=None, quantity=0, coins=total_coins))

    return ledger.record(
        character=character,
        kind=LedgerEntry.Kind.AWARD,
        lines=entry_lines,
        note="Starting equipment",
        actor=actor,
    )


# Backward-compatible module-level function wrapper
__all__ = ["apply_starting_equipment"]