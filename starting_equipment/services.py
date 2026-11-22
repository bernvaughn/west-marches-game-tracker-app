"""Services for starting equipment application."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Q

from ledger.models import LedgerEntry, LedgerLine
from ledger.services import record as ledger_record
from player_characters import life
from player_characters.models import Character

if TYPE_CHECKING:
    from accounts.models import User
    from items.models import Item
    from starting_equipment.models import StartingEquipmentTemplate


class StartingEquipmentError(Exception):
    """Base exception for starting equipment service errors."""


class AlreadyClaimed(StartingEquipmentError):
    """Raised when starting equipment has already been claimed for a character."""


class InvalidChoices(StartingEquipmentError):
    """Raised when the player's choice picks are missing or invalid."""


class CharacterCannotClaim(StartingEquipmentError):
    """Raised when a dead or archived character cannot claim starting equipment."""

    pass


@dataclass(frozen=True)
class Reason:
    """A plain-language explanation of why some gear was not granted."""

    code: str
    message: str


@dataclass(frozen=True)
class ChoiceOption:
    """One selectable line within a starting equipment choice group."""

    line_id: int
    item: "Item"
    quantity: int


@dataclass(frozen=True)
class ChoiceGroup:
    """One 'X or Y' choice group the player must pick exactly one option from."""

    key: str
    source: str
    slug: str
    label: str
    options: list[ChoiceOption]


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
                ranges = [f"levels {e.min_level}-{e.max_level}" for e in qs.order_by("min_level")]
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
        if (
            background_option_id is not None
            and not template.background_entries.filter(
                background_option_id=background_option_id
            ).exists()
        ):
            reasons.append(Reason("background_no_entry", _background_no_entry_message(character)))

    return reasons


# ---------------------------------------------------------------------------
# Choice groups (pure: no writes)
# ---------------------------------------------------------------------------


def _slug_label(slug: str) -> str:
    """Turn a choice_group slug into a readable label (gaming_set -> Gaming set)."""
    return slug.replace("_", " ").capitalize()


def _matched_entries(character: "Character", template: "StartingEquipmentTemplate"):
    """Return (class_entry, bg_entry) matched to the character's options/level.

    Pure: no writes. Either entry may be None when there is no match.
    """
    character_level = character.level or 1
    class_entry = None
    if character.class_option:
        class_entry = (
            template.class_entries.filter(class_option=character.class_option)
            .filter(
                Q(min_level__lte=character_level) & Q(max_level__gte=character_level),
            )
            .first()
        )
    bg_entry = None
    if character.background_option:
        bg_entry = template.background_entries.filter(
            background_option=character.background_option,
        ).first()
    return class_entry, bg_entry


def _choice_groups_for_lines(source: str, lines) -> list[ChoiceGroup]:
    """Group choice lines by choice_group slug, ordered by line id."""
    by_group: dict[str, list] = {}
    for line in lines.select_related("item").order_by("id"):
        if not line.is_choice or not line.choice_group:
            continue
        by_group.setdefault(line.choice_group, []).append(line)
    groups: list[ChoiceGroup] = []
    for slug, group_lines in by_group.items():
        groups.append(
            ChoiceGroup(
                key=f"{source}:{slug}",
                source=source,
                slug=slug,
                label=f"{source.title()}: {_slug_label(slug)}",
                options=[ChoiceOption(line.id, line.item, line.quantity) for line in group_lines],
            )
        )
    return groups


def _choice_groups_for_entries(class_entry, bg_entry) -> list[ChoiceGroup]:
    """Return the choice groups for a class and/or background entry."""
    groups: list[ChoiceGroup] = []
    if class_entry is not None:
        groups.extend(_choice_groups_for_lines("class", class_entry.lines.all()))
    if bg_entry is not None:
        groups.extend(_choice_groups_for_lines("background", bg_entry.lines.all()))
    return groups


def get_choice_groups(
    character: "Character", template: "StartingEquipmentTemplate | None"
) -> list[ChoiceGroup]:
    """Return the choice groups a player must pick from for this character.

    Pure: no writes. Returns [] when the template is None, belongs to another
    club, or the matched entries have no choice groups.
    """
    if template is None:
        return []
    if getattr(template, "club_id", None) != getattr(character, "club_id", None):
        return []
    class_entry, bg_entry = _matched_entries(character, template)
    return _choice_groups_for_entries(class_entry, bg_entry)


# ---------------------------------------------------------------------------
# Apply (writes a ledger entry)
# ---------------------------------------------------------------------------


def _granted_lines(entry_lines, picks=None) -> list[LedgerLine]:
    """Return the ledger lines a claim grants from one class/background entry.

    Every fixed line (is_choice=False) is granted. For each non-empty
    choice_group:
    - when picks is given (slug -> line id), only the picked line is granted;
    - otherwise only the first line by id (the seeded default) is granted.

    Choice lines with an empty choice_group are never granted.

    Args:
        entry_lines: The lines of one entry (class or background).
        picks: Optional mapping of choice_group slug to the chosen line id.

    Returns:
        List of LedgerLine to grant.
    """
    picks = picks or {}
    granted = []
    seen_groups = set()
    for line in entry_lines.select_related("item").order_by("id"):
        if line.is_choice:
            if not line.choice_group:
                continue
            if picks:
                if line.id == picks.get(line.choice_group):
                    granted.append(LedgerLine(item=line.item, quantity=line.quantity, coins=0))
                continue
            if line.choice_group in seen_groups:
                continue
            seen_groups.add(line.choice_group)
        granted.append(LedgerLine(item=line.item, quantity=line.quantity, coins=0))
    return granted


def apply_starting_equipment(
    character: "Character",
    template: "StartingEquipmentTemplate | None",
    actor: "User | None",
    picks: dict[str, int] | None = None,
) -> StartingEquipmentResult:
    """
    Apply starting equipment for a character.

    Creates one ledger entry with all granted items and coins.
    Returns a StartingEquipmentResult with the ledger entry (or None) and
    a list of reasons explaining why any gear was not granted.

    Choice groups: for each class/background entry, all non-choice lines are
    granted, plus exactly one picked line per non-empty choice_group.

    When ``picks`` is given it maps each group key ("class:<slug>" /
    "background:<slug>") to the chosen line id. Every group must have a valid
    pick (a line that belongs to that group's matched entry) or
    ``InvalidChoices`` is raised. When ``picks`` is None the first line (by id)
    of each group is granted, which keeps the previous default-pick behaviour.

    Args:
        character: The character to grant equipment to.
        template: The starting equipment template to use (may be None).
        actor: The user performing the grant (can be None).
        picks: Optional mapping of group key to chosen line id.

    Returns:
        StartingEquipmentResult with entry and reasons.
    """
    reasons = explain_starting_equipment(character, template)

    # No template or empty template: nothing to grant, no write.
    if any(reason.code in ("no_template", "empty_template") for reason in reasons):
        return StartingEquipmentResult(entry=None, reasons=reasons)

    # Validate picks against the current groups when they are provided.
    class_picks: dict[str, int] = {}
    bg_picks: dict[str, int] = {}
    if picks:
        class_entry, bg_entry = _matched_entries(character, template)
        groups = _choice_groups_for_entries(class_entry, bg_entry)
        group_by_key = {group.key: group for group in groups}
        for key, line_id in picks.items():
            group = group_by_key.get(key)
            if group is None or line_id not in {option.line_id for option in group.options}:
                raise InvalidChoices(
                    f"Invalid pick for group {key}: line {line_id} is not an option."
                )
        for group in groups:
            if group.key not in picks:
                raise InvalidChoices(f"Missing pick for group {group.key}.")
        class_picks = {group.slug: picks[group.key] for group in groups if group.source == "class"}
        bg_picks = {
            group.slug: picks[group.key] for group in groups if group.source == "background"
        }

    lines: list[LedgerLine] = []
    total_coins = 0

    # 1. Class equipment - match by class_option FK + level range
    character_level = character.level or 1
    class_entry, bg_entry = _matched_entries(character, template)

    if class_entry:
        # Add class coins
        total_coins += class_entry.coins_cp

        lines.extend(_granted_lines(class_entry.lines, picks=class_picks))

    # 2. Background equipment - only if character has background_option
    if bg_entry is not None:
        # Add background coins
        total_coins += bg_entry.coins_cp

        lines.extend(_granted_lines(bg_entry.lines, picks=bg_picks))

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


def claim_starting_equipment(
    character: "Character",
    template: "StartingEquipmentTemplate | None",
    actor: "User | None",
    picks: dict[str, int] | None = None,
) -> StartingEquipmentResult:
    """Claim starting equipment exactly once, atomically.

    Re-checks ``starting_equipment_claimed`` inside a row lock so a concurrent
    or repeated claim can never grant twice. Sets the claimed flag only when an
    entry is actually granted, so a template that grants nothing leaves the
    character unclaimed and able to retry later.

    Args:
        character: The character to claim for.
        template: The active starting equipment template (may be None).
        actor: The user performing the claim.
        picks: Optional mapping of group key to chosen line id.

    Returns:
        StartingEquipmentResult with the granted entry (or None) and reasons.

    Raises:
        AlreadyClaimed: If starting equipment was already claimed.
    """
    with transaction.atomic():
        locked = Character.objects.select_for_update().get(pk=character.pk)
        if not life.can_act(locked):
            raise CharacterCannotClaim(life.act_block_reason(locked))
        if locked.starting_equipment_claimed:
            raise AlreadyClaimed("Starting equipment has already been claimed for this character.")
        result = apply_starting_equipment(locked, template, actor, picks=picks)
        if result.entry is not None:
            locked.starting_equipment_claimed = True
            locked.save(update_fields=["starting_equipment_claimed"])
        return result


# Backward-compatible module-level function wrapper
__all__ = [
    "apply_starting_equipment",
    "claim_starting_equipment",
    "explain_starting_equipment",
    "get_choice_groups",
    "AlreadyClaimed",
    "InvalidChoices",
    "CharacterCannotClaim",
    "Reason",
    "ChoiceOption",
    "ChoiceGroup",
    "StartingEquipmentResult",
]
