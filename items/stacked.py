"""Pricing and labels for stacked items.

Pure functions: no Django imports, no database access, integer math only.

A stacked item is sold in bundles but used one unit at a time (parchment by
the sheet, rope by the foot, arrows by the arrow). ``value_cp`` is the price
that ``value_units`` units cover; for normal items ``value_units`` is 1.

Decisions made without the owner, recorded here so slice owners can rely on
them:

- Unit names are never pluralised, so ``bundle_label`` says "bundle of 100
  arrow" (the spec example shows "arrows"; flagged to the owner).
- A 0 cp sale is refused by the slices; ``sale_price`` itself returns 0 with
  no minimum (no 1 cp floor).
- ``bundle_price`` uses ceil with no 1 cp minimum; ``percent_price`` for
  normal items is unchanged and keeps its 1 cp minimum.
- Non-stacked items always have ``bundle_units == 1`` (enforced by
  forms/services, not the DB); ``bundle_label`` returns the item name for
  them.

These pure functions remain for backward compatibility. Application code
should import :class:`items.services.StackedPricingService` instead and call
its static methods (``sale_price``, ``bundle_price``, ``unit_label``,
``bundle_label``).
"""

from numbers import Integral


def _require_positive(value, name):
    """Validate that ``value`` is a non-bool positive integer."""
    if not isinstance(value, Integral) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _require_percent(value, name):
    """Validate that ``value`` is a non-bool integer percent, 0 or more.

    0% is valid shop data (the manage form allows 0-1000) and prices to 0.
    """
    if not isinstance(value, Integral) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def bundle_price(item, bundle_units, sell_percent):
    """Price of one bundle of ``bundle_units`` units at ``sell_percent``.

    ``ceil(value_cp * bundle_units * sell_percent / (100 * value_units))``.
    Integer math only; no 1 cp minimum.
    """
    _require_positive(bundle_units, "bundle_units")
    _require_percent(sell_percent, "sell_percent")
    v = item.value_cp
    vu = item.value_units
    return -(-(v * bundle_units * sell_percent) // (100 * vu))


def sale_price(item, units, buy_percent):
    """Revenue from selling ``units`` units at ``buy_percent``.

    ``floor(value_cp * units * buy_percent / (100 * value_units))``.
    Integer math once from the total units sold, never per unit. No 1 cp
    minimum (may return 0; slices refuse a 0 cp sale).
    """
    _require_positive(units, "units")
    _require_percent(buy_percent, "buy_percent")
    v = item.value_cp
    vu = item.value_units
    return (v * units * buy_percent) // (100 * vu)


def unit_label(item, qty):
    """Label for a quantity of an item.

    Stacked: "40 ft Rope". Normal: "3 × Rope".
    """
    if not isinstance(qty, Integral) or isinstance(qty, bool) or qty < 1:
        raise ValueError("qty must be a positive integer")
    if item.is_stacked:
        return f"{qty} {item.unit_name} {item.name}"
    return f"{qty} × {item.name}"


def bundle_label(item, bundle_units):
    """Label for a shop bundle line.

    Stacked: "bundle of 100 arrow" (unit name never pluralised).
    Non-stacked: the item name (bundle_units is 1 for non-stacked items).
    """
    _require_positive(bundle_units, "bundle_units")
    if item.is_stacked:
        return f"bundle of {bundle_units} {item.unit_name}"
    return item.name
