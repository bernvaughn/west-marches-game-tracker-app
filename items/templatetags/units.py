"""Template filters for stacked-item units and bundle labels.

Usage::

    {% load units %}
    {{ item|with_units:qty }}
    {{ item|bundle_label:n }}
    {{ item|item_value }}
"""

from django import template

from items.services import StackedPricingService
from items.values import format_item_value

register = template.Library()


@register.filter
def with_units(item, qty):
    """Render a quantity with the item's unit name.

    Stacked: "40 ft Rope". Normal: "3 × Rope".
    """
    return StackedPricingService.unit_label(item, qty)


@register.filter
def bundle_label(item, n):
    """Render a shop bundle line label.

    Stacked: "bundle of 100 arrow". Non-stacked: the item name.
    """
    return StackedPricingService.bundle_label(item, n)


@register.filter
def item_value(item):
    """Format an item's value for display.

    Returns empty string for None. Uses format_item_value for plain,
    stacked, and no-value items.
    """
    if item is None:
        return ""
    return format_item_value(item)
