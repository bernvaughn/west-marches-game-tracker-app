"""Helpers for the character sheet: ability modifiers and passive Perception."""

from .models import ABILITIES

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
