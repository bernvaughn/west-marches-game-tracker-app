"""Template filters for item weight display.

Usage::

    {% load weights %}
    {{ item.weight_hundredth_lb|weight_display }}
    {{ item.weight_hundredth_lb|weight_display:2 }}
    {{ item|weight_total:qty|weight_display:2 }}
"""

from django import template

from items.weights import format_weight, item_weight_total

register = template.Library()


@register.filter
def weight_display(hundredths, precision=1):
    """Format weight in hundredths of a pound for display.

    Args:
        hundredths: Weight in hundredths of a pound, or None.
        precision: Decimal places (default 1, use 2 for stacked totals).

    Returns:
        Formatted string like "1.3 lb" or "not listed".
    """
    return format_weight(hundredths, precision)


@register.filter
def weight_total(item, qty):
    """Calculate total weight for a quantity of an item.

    Args:
        item: An Item instance.
        qty: Number of units.

    Returns:
        Total weight in hundredths of a pound, or None if item has no weight.
    """
    return item_weight_total(item, qty)
