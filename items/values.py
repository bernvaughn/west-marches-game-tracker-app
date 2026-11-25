"""Value formatting helpers for items."""

from ledger.coins import format_coins

NO_VALUE_TEXT = "no value"


def format_item_value(item):
    """
    Format an item's value for display in the picker.

    Args:
        item: An Item instance.

    Returns:
        Formatted string:
        - Plain item (not stacked): coin format (e.g. "15 gp") or "no value" if 0.
        - Stacked item: "N gp per <unit>" where N = value_cp/100/value_units.
        - Zero/blank value: "no value".
    """
    if item.value_cp == 0:
        return NO_VALUE_TEXT

    if item.is_stacked:
        # For stacked items, show value per unit
        # value_cp is the value for value_units units
        # So value per unit = value_cp / value_units
        value_per_unit_cp = item.value_cp // item.value_units
        if value_per_unit_cp == 0:
            return NO_VALUE_TEXT
        unit = item.unit_name or "unit"
        gp_value = value_per_unit_cp // 100
        if gp_value == 0:
            return NO_VALUE_TEXT
        return f"{gp_value} gp per {unit}"

    # Plain item
    return format_coins(item.value_cp)
