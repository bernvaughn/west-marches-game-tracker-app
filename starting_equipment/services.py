"""Services for starting equipment application."""

from typing import TYPE_CHECKING

from django.db.models import Q

from ledger.models import LedgerEntry, LedgerLine
from ledger.services import record as ledger_record

if TYPE_CHECKING:
    from accounts.models import User
    from player_characters.models import Character
    from starting_equipment.models import StartingEquipmentTemplate


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

    # 1. Class equipment - match by class_option FK + level range
    character_level = character.level or 1
    class_entry = None
    if character.class_option:
        class_entry = (
            template.class_entries.filter(
                class_option=character.class_option,
            )
            .filter(
                Q(min_level__lte=character_level) & Q(max_level__gte=character_level),
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

    # 2. Background equipment - only if character has background_option
    if character.background_option:
        bg_entry = template.background_entries.filter(
            background_option=character.background_option,
        ).first()

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

    # Note: approved magic item requests are already granted immediately by
    # request_decide (approve). They are intentionally NOT re-granted here to
    # avoid a double grant when the character later claims starting equipment.

    # If nothing to grant, return None
    if not lines and total_coins == 0:
        return None

    # Create the ledger entry
    entry_lines = lines.copy()
    if total_coins > 0:
        entry_lines.append(LedgerLine(item=None, quantity=0, coins=total_coins))

    return ledger_record(
        character=character,
        kind=LedgerEntry.Kind.AWARD,
        lines=entry_lines,
        note="Starting equipment",
        actor=actor,
    )


# Backward-compatible module-level function wrapper
__all__ = ["apply_starting_equipment"]
