"""Expected value computation for downtime reward tables."""

from items.values import format_item_value
from ledger.coins import format_coins


def item_value_cp(item, quantity=1):
    """
    Copper value of `quantity` of `item`.

    Returns 0 if no item or no value.
    Stacked items use value_cp * quantity // value_units.
    """
    if item is None or item.value_cp == 0:
        return 0

    if item.is_stacked:
        # value_cp is the value for value_units units
        return item.value_cp * quantity // item.value_units

    return item.value_cp * quantity


def entry_value_cp(entry):
    """
    Sum of item values in copper for one entry.

    Also includes the entry's coins field (already in copper).
    Handles both Django model instances and simple objects with .items attribute.
    """
    total = entry.coins or 0
    items = entry.items.all() if hasattr(entry.items, "all") else entry.items
    for entry_item in items:
        item = entry_item.item if hasattr(entry_item, "item") else entry_item
        qty = entry_item.quantity if hasattr(entry_item, "quantity") else 1
        total += item_value_cp(item, qty)
    return total


def expected_value_cp(entries):
    """
    Expected value of a weighted table in copper.

    Formula: sum(weight * entry_value) / total_weight
    Entries with no value count as zero.
    Returns 0 when total weight is 0.
    """
    total_weight = sum(e.weight for e in entries if e.weight)
    if total_weight == 0:
        return 0

    weighted_sum = sum(e.weight * entry_value_cp(e) for e in entries)
    return weighted_sum // total_weight


def expected_value(entries):
    """Formatted expected value in the usual coin form."""
    ev_cp = expected_value_cp(entries)
    if ev_cp == 0:
        return ""
    return format_coins(ev_cp)


def entry_value_text(entry):
    """
    Display text for an entry's value using format_item_value per item.

    Returns a string like "15 gp, 5 gp per ft Rope" or empty string if no value.
    """
    parts = []
    if entry.coins:
        from ledger.coins import format_coins

        parts.append(format_coins(entry.coins))

    for entry_item in entry.items.all():
        item = entry_item.item
        if item and item.value_cp:
            val_text = format_item_value(item)
            if entry_item.quantity > 1:
                val_text = f"{entry_item.quantity} x {val_text}"
            parts.append(val_text)

    return ", ".join(parts) if parts else ""
