"""Helpers for the character sheet: ability modifiers, passive Perception and XP progress."""

from .models import ABILITIES
from .xp_levels import MAX_LEVEL, level_for_xp, next_threshold, progress_fraction

DASH = "—"
MINUS = "−"

ABILITY_FIELDS = {name for name, _abbr, _label in ABILITIES}


def edit_current_values(form):
    """Display text for the saved value of each field on the character edit form.

    The values come from form.saved_values (or form.initial), which hold the
    record as saved. A failed is_valid() has already copied the submitted
    values onto form.instance, so the instance is never safe to read here.
    """
    values = {}
    for name, value in getattr(form, "saved_values", form.initial).items():
        if name not in form.fields:
            continue
        if name in ABILITY_FIELDS:
            modifier = format_modifier(ability_modifier(value))
            values[name] = f"{value} ({modifier})" if value is not None else DASH
        elif value is None:
            values[name] = DASH
        elif isinstance(value, str):
            values[name] = value.strip() or DASH
        else:
            values[name] = str(value)
    return values


def ability_modifier(score):
    """D&D modifier for a score, or None when the score is blank."""
    if score is None:
        return None
    return (score - 10) // 2


def format_modifier(mod):
    if mod is None:
        return DASH
    return f"+{mod}" if mod >= 0 else f"{MINUS}{-mod}"


def passive_perception(bonus):
    """10 plus the bonus. None when the bonus is blank."""
    if bonus is None:
        return None
    return 10 + bonus


def passive_perception_label(bonus):
    if bonus is None:
        return DASH
    sign = "+" if bonus >= 0 else MINUS
    return f"{10 + bonus} (10 {sign} {abs(bonus)})"


def ability_rows(character):
    rows = []
    for field, abbr, label in ABILITIES:
        score = getattr(character, field)
        rows.append(
            {
                "field": field,
                "abbr": abbr,
                "label": label,
                "score": DASH if score is None else score,
                "modifier": format_modifier(ability_modifier(score)),
            }
        )
    return rows


def xp_progress(character):
    """XP progress for the sheet, or None when XP is blank.

    The bar is driven by XP alone. The stored level only drives the
    "level up ready" badge and the max-level check. The app never
    changes the level itself.
    """
    if character.xp is None:
        return None
    xp = character.xp
    level = character.level
    xp_level = level_for_xp(xp)
    threshold = next_threshold(xp)
    # "Max level" follows the stored level. A blank level falls back to XP.
    # A stored level below 20 with 355,000+ XP still gets the badge.
    if level is None:
        is_max = threshold is None
    else:
        is_max = level >= MAX_LEVEL
    level_up_ready = level is not None and level < xp_level
    progress = {
        "xp": xp,
        "xp_level": xp_level,
        "next_level": None if threshold is None else xp_level + 1,
        "next_threshold": threshold,
        "percent": int(progress_fraction(xp) * 100),
        "is_max": is_max,
        "level_up_ready": level_up_ready,
    }
    if threshold is not None:
        progress["xp_label"] = f"{xp:,} / {threshold:,} XP to level {xp_level + 1}"
    else:
        progress["xp_label"] = f"{xp:,} XP (level {MAX_LEVEL} reached)"
    return progress
