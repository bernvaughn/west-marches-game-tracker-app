"""Weight formatting and calculation helpers for items.

Pure functions: no Django imports, no database access, integer math only.

Weight is stored as hundredths of a pound (integer) to avoid float issues.
None means "not listed", never zero.

Decisions made without the owner, recorded here so slice owners can rely on them:

- Blank weight displays as "not listed" and is never treated as zero.
- For stacked items the weight is per unit and totals scale with units.
- Weight displays with one decimal place (two for stacked sub-unit items).
- Weight never blocks a buy, sale, award, or opening.
"""

from decimal import ROUND_HALF_UP, Decimal


def format_weight(hundredths: int | None, precision: int = 1) -> str:
    """Format weight in hundredths of a pound as a string.

    Args:
        hundredths: Weight in hundredths of a pound, or None for "not listed".
        precision: Number of decimal places (default 1, use 2 for stacked totals).

    Returns:
        Formatted string like "1.3 lb" or "not listed".
    """
    if hundredths is None:
        return "not listed"
    # Convert hundredths to pounds with specified precision using Decimal for proper rounding
    pounds = Decimal(hundredths) / Decimal(100)
    quantizer = Decimal(10) ** -precision
    rounded = pounds.quantize(quantizer, rounding=ROUND_HALF_UP)
    return f"{rounded:.{precision}f} lb"


def item_weight_total(item, units: int) -> int | None:
    """Calculate total weight in hundredths for a quantity of an item.

    Args:
        item: An Item instance (must have weight_hundredth_lb and is_stacked fields).
        units: Number of units.

    Returns:
        Total weight in hundredths of a pound, or None if item has no weight.
    """
    if item.weight_hundredth_lb is None:
        return None
    if item.is_stacked:
        return item.weight_hundredth_lb * units
    # Non-stacked items: weight is for the single item, units ignored (always 1)
    return item.weight_hundredth_lb
