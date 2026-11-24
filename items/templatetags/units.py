"""Template filters for stacked-item units and bundle labels.

Usage::

    {% load units %}
    {{ item|with_units:qty }}
    {{ item|bundle_label:n }}
"""

from django import template

from items.services import StackedPricingService

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
    return stacked.bundle_label(item, n)
