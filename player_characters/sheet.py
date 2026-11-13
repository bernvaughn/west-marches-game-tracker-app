"""Helpers for the character sheet: ability modifiers and passive Perception."""

from .models import ABILITIES

DASH = "—"
MINUS = "−"


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
