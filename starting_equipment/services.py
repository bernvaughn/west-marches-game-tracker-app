"""Services for starting equipment application."""

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Reason:
    """A plain-language explanation of why some gear was not granted."""

    code: str
    message: str


@dataclass(frozen=True)
class StartingEquipmentResult:
    """Outcome of applying starting equipment to a character."""

    entry: "LedgerEntry | None"
    reasons: list[Reason]

    @property
    def granted(self) -> bool:
        """True if at least one item or coin line was granted."""
        return self.entry is not None


# ---------------------------------------------------------------------------
# Reason messages
# ---------------------------------------------------------------------------


def _no_template_message() -> str:
    return "No starting equipment template exists for this club. Ask a club admin to create one."


def _empty_template_message() -> str:
    return (
        "This starting equipment template has no class entries, background entries, "
        "or level coins, so there is nothing to grant."
    )


def _class_missing_message() -> str:
    return (
        "No class is set on this character, so no class gear will be granted. "
        "Ask a club admin if you expected one."
    )


def _class_custom_message(character: "Character") -> str:
    return (
        f"No starting gear for class '{character.char_class}': "
        "it is a custom value. Ask a club admin to add it as a class."
    )


def _class_no_entry_message(character: "Character") -> str:
    return (
        f"No starting gear for class '{character.char_class}': "
        "this template has no entry for that class. Ask a club admin to add one."
    )


def _class_level_not_covered_message(character: "Character", level: int, ranges: list[str]) -> str:
    range_text = "; ".join(ranges)
    return (
        f"No starting gear for class '{character.char_class}' at level {level}: "
        f"this template covers {range_text}. "
        "Ask a club admin to add a level range that includes this level."
    )


def _background_missing_message() -> str:
    return (
        "No background is set on this character, so no background gear will be granted. "
        "Ask a club admin if you expected one."
    )


def _background_custom_message(character: "Character") -> str:
    return (
        f"No starting gear for background '{character.background}': "
        "it is a custom value. Ask a club admin to add it as a background."
    )


def _background_no_entry_message(character: "Character") -> str:
    return (
        f"No starting gear for background '{character.background}': "
        "this template has no entry for that background. "
        "Ask a club admin to add one."
    )


# ---------------------------------------------------------------------------
# Pure explanation (no writes)
# ---------------------------------------------------------------------------


def explain_starting_equipment(
    character: "Character",
    template: "StartingEquipmentTemplate | None",
) -> list[Reason]:
    """
    Return the list of reasons why starting equipment may not be granted.

    Pure: no writes. Reasons are additive - a granted entry can still carry
    reasons (for example class matched but background custom).

    Codes:
    - no_template: template is None or belongs to another club.
    - empty_template: template has no class entries, background entries or level coins.
    - class_missing: class text blank and no class_option FK.
    - class_custom: class text set, class_option None.
    - class_no_entry: class_option set, template has no entry for it.
    - class_level_not_covered: entries exist for the record, none covers the level.
    - background_missing / background_custom / background_no_entry: same rules.

    Args:
        character: The character to explain equipment for.
        template: The starting equipment template, or None.

    Returns:
        List of Reason (code plus plain message), possibly empty.
    """
    reasons: list[Reason] = []

    # 0. Template missing or in another club.
    if template is None:
        reasons.append(Reason("no_template", _no_template_message()))
        return reasons
    if getattr(template, "club_id", None) != getattr(character, "club_id", None):
        reasons.append(Reason("no_template", _no_template_message()))
        return reasons

    # 1. Empty template short-circuits everything else.
    if not (
        template.class_entries.exists()
        or template.background_entries.exists()
        or template.level_coins.exists()
    ):
        reasons.append(Reason("empty_template", _empty_template_message()))
        return reasons

    character_level = character.level or 1

    # 2. Class.
    class_option_id = getattr(character, "class_option_id", None)
    class_text = (getattr(character, "char_class", "") or "").strip()
    if not class_text and class_option_id is None:
        reasons.append(Reason("class_missing", _class_missing_message()))
    elif class_text and class_option_id is None:
        reasons.append(Reason("class_custom", _class_custom_message(character)))
    else:
        # class_option is set: look for an entry covering the character's level.
        qs = template.class_entries.filter(class_option_id=class_option_id)
        if not qs.exists():
            reasons.append(Reason("class_no_entry", _class_no_entry_message(character)))
        else:
            covered = qs.filter(
                Q(min_level__lte=character_level) & Q(max_level__gte=character_level)
            ).exists()
            if not covered:
                ranges = [
                    f"levels {e.min_level}-{e.max_level}" for e in qs.order_by("min_level")
                ]
                reasons.append(
                    Reason(
                        "class_level_not_covered",
                        _class_level_not_covered_message(character, character_level, ranges),
                    )
                )

    # 3. Background.
    background_option_id = getattr(character, "background_option_id", None)
    background_text = (getattr(character, "background", "") or "").strip()
    if not background_text and background_option_id is None:
        reasons.append(Reason("background_missing", _background_missing_message()))
    elif background_text and background_option_id is None:
        reasons.append(Reason("background_custom", _background_custom_message(character)))
    else:
        if background_option_id is not None and not template.background_entries.filter(
            background_option_id=background_option_id
        ).exists():
            reasons.append(Reason("background_no_entry", _background_no_entry_message(character)))

    return reasons


# ---------------------------------------------------------------------------
# Apply (writes a ledger entry)
# ---------------------------------------------------------------------------


def apply_starting_equipment(
    character: "Character",
    template: "StartingEquipmentTemplate | None",
    actor: "User | None",
) -> StartingEquipmentResult:
    """
    Apply starting equipment for a new character.

    Creates one ledger entry with all granted items and coins.
    Returns a StartingEquipmentResult with the ledger entry (or None) and
    a list of reasons explaining why any gear was not granted.

    Args:
        character: The new character to grant equipment to.
        template: The starting equipment template to use (may be None).
        actor: The user performing the grant (can be None).

    Returns:
        StartingEquipmentResult with entry and reasons.
    """
    reasons = explain_starting_equipment(character, template)

    # No template or empty template: nothing to grant, no write.
    if any(reason.code in ("no_template", "empty_template") for reason in reasons):
        return StartingEquipmentResult(entry=None, reasons=reasons)

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

    # If nothing to grant, return None (but keep the reasons)
    if not lines and total_coins == 0:
        return StartingEquipmentResult(entry=None, reasons=reasons)

    # Create the ledger entry
    entry_lines = lines.copy()
    if total_coins > 0:
        entry_lines.append(LedgerLine(item=None, quantity=0, coins=total_coins))

    entry = ledger_record(
        character=character,
        kind=LedgerEntry.Kind.AWARD,
        lines=entry_lines,
        note="Starting equipment",
        actor=actor,
    )

    return StartingEquipmentResult(entry=entry, reasons=reasons)


# Backward-compatible module-level function wrapper
__all__ = ["apply_starting_equipment", "explain_starting_equipment", "Reason", "StartingEquipmentResult"]
