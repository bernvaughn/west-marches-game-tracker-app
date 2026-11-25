"""Carried weight and carrying capacity for the character sheet.

Pure logic over inventory rows: sums item weight x units, with a default
capacity of 15 x Strength. Weight is informational only and never blocks
anything (a buy over capacity still succeeds).

Weight is stored as hundredths of a pound (integer) to avoid float problems.
None means "not listed", never zero.
"""

from decimal import Decimal


def calculate_carried_weight(inventory_rows, character=None, club_weight_settings=None):
    """Sum carried weight over inventory rows, including coin weight if enabled.

    Returns (total_hundredths, unweighted_count, unweighted_names).

    total_hundredths is the sum of item.weight_hundredth_lb * units over all
    rows whose item has a weight listed, plus coin weight when enabled.
    units is row.owned (stacked items use the owned quantity as units;
    non-stacked items weigh once per owned item).
    unweighted_names lists the names of items with no weight listed.
    """
    total = 0
    unweighted_names = []
    for row in inventory_rows:
        item = row.item
        units = row.owned
        if item.weight_hundredth_lb is None:
            unweighted_names.append(item.name)
        else:
            total += item.weight_hundredth_lb * units

    # Add coin weight when enabled and character provided
    if character is not None and club_weight_settings is not None:
        from player_characters.coin_weight import coin_weight_hundredths

        total += coin_weight_hundredths(character, club_weight_settings)

    return total, len(unweighted_names), unweighted_names


def default_capacity(character) -> int | None:
    """Default carrying capacity in hundredths of a pound: 15 x Strength.

    Returns None when Strength is blank.
    """
    if character.strength is not None:
        return character.strength * 15 * 100
    return None


def carrying_capacity(character) -> int | None:
    """Carrying capacity for the character.

    Manual override (carrying_capacity_lb) replaces default if set.
    Otherwise uses 15 x Strength.
    """
    if character.carrying_capacity_lb is not None:
        return character.carrying_capacity_lb * 100
    return default_capacity(character)


def _format_pounds(hundredths: int) -> str:
    """Format hundredths of a pound as pounds, stripping trailing zeros."""
    pounds = Decimal(hundredths) / Decimal(100)
    text = format(pounds, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text} lb"


def format_carrying_line(total_hundredths: int, capacity_hundredths: int | None) -> str:
    """Build the sheet's carrying line.

    With capacity: "Carrying X lb of Y lb".
    Without capacity: "Carrying X lb".
    """
    total_text = _format_pounds(total_hundredths)
    if capacity_hundredths is not None:
        return f"Carrying {total_text} of {_format_pounds(capacity_hundredths)}"
    return f"Carrying {total_text}"


def over_capacity(total_hundredths: int, capacity_hundredths: int | None) -> bool:
    """True when carried weight exceeds capacity. No capacity means never over."""
    if capacity_hundredths is None:
        return False
    return total_hundredths > capacity_hundredths
