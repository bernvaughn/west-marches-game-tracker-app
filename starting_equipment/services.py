"""Starting equipment service: applies starting equipment templates to new characters."""

from accounts.models import User
from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.models import Character

from .models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentClassEntry,
    StartingEquipmentLevelCoins,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)


def apply_starting_equipment(
    character: Character,
    template: StartingEquipmentTemplate,
    actor: User,
) -> LedgerEntry | None:
    """
    Apply starting equipment for a new character based on a template.

    Creates one ledger entry with all granted items and coins.
    Returns the ledger entry, or None if no lines to grant.

    Args:
        character: The character to equip.
        template: The starting equipment template to use.
        actor: The user performing the action (for audit trail).

    Returns:
        The created LedgerEntry, or None if no equipment was granted.
    """
    lines: list[Line] = []

    # 1. Class equipment (case-insensitive match, level range filter)
    level = character.level or 1
    class_entry = (
        StartingEquipmentClassEntry.objects.filter(
            template=template,
            char_class__iexact=character.char_class,
            min_level__lte=level,
            max_level__gte=level,
        )
        .select_related("template")
        .prefetch_related("lines__item")
        .first()
    )
    if class_entry:
        for line in class_entry.lines.all():
            if not line.is_choice:  # Choices handled in UI, grant first option
                lines.append(Line(line.item, line.quantity))
        if class_entry.coins_cp:
            lines.append(Line(coins=class_entry.coins_cp))

    # 2. Background equipment (case-insensitive match)
    if character.background:
        bg_entry = (
            StartingEquipmentBackgroundEntry.objects.filter(
                template=template,
                background__iexact=character.background,
            )
            .select_related("template")
            .prefetch_related("lines__item")
            .first()
        )
        if bg_entry:
            for line in bg_entry.lines.all():
                if not line.is_choice:
                    lines.append(Line(line.item, line.quantity))
            if bg_entry.coins_cp:
                lines.append(Line(coins=bg_entry.coins_cp))

    # 3. Level-based coins (for level > 1)
    if level > 1:
        level_coins = StartingEquipmentLevelCoins.objects.filter(
            template=template, level=level
        ).first()
        if level_coins:
            lines.append(Line(coins=level_coins.coins_cp))

    # 4. Approved magic item requests (status=APPROVED only)
    approved_requests = StartingEquipmentRequest.objects.filter(
        character=character, status=StartingEquipmentRequest.Status.APPROVED
    ).select_related("item")
    for req in approved_requests:
        lines.append(Line(req.item, req.quantity))

    if not lines:
        return None

    return record(
        character=character,
        kind="award",
        lines=lines,
        note="Starting equipment",
        actor=actor,
    )