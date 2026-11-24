"""Shared pure property tests for stacked item pricing.

Pure tests: ``SimpleNamespace`` stand-in items, no database. The two
mathematical properties of ``items/stacked.py`` are asserted once here and
reused by ``items/tests/test_stacked_pricing.py`` and
``shops/tests/test_u129_sell_units.py`` so they run in both modules without
duplicated test code.
"""

from types import SimpleNamespace

import pytest

from items.stacked import bundle_price, sale_price


def _make_pure_item(value_cp, value_units, name="Thing", unit_name="unit", stacked=True):
    """Build a pure stand-in item with the fields ``stacked.py`` reads."""
    return SimpleNamespace(
        name=name,
        unit_name=unit_name,
        value_cp=value_cp,
        value_units=value_units,
        is_stacked=stacked,
    )


def _split_sale_total(it, units, buy_percent, parts):
    """Total revenue from selling ``units`` in ``parts`` at ``buy_percent``."""
    return sum(sale_price(it, p, buy_percent) for p in parts if p >= 1)


def assert_split_sales_never_beat_one_sale(it, units, buy_percent, *parts_lists):
    """Assert selling in parts never beats selling all ``units`` at once."""
    total = sale_price(it, units, buy_percent)
    for parts in parts_lists:
        assert _split_sale_total(it, units, buy_percent, parts) <= total


def assert_buy_then_sell_back_never_profits(it, bundle, sell_percent, buy_percent):
    """Assert buying ``bundle`` then selling it back never profits when sell >= buy."""
    cost = bundle_price(it, bundle, sell_percent)
    revenue = sale_price(it, bundle, buy_percent)
    assert revenue <= cost, (
        f"profit: buy {bundle} for {cost} cp, sell back for {revenue} cp "
        f"(sell {sell_percent}% >= buy {buy_percent}%)"
    )


@pytest.mark.story("U129")
@pytest.mark.parametrize("value_cp", [0, 1, 3, 7, 13, 25, 50, 100, 300])
@pytest.mark.parametrize("value_units", [1, 2, 3, 7, 10, 20, 50])
@pytest.mark.parametrize("buy_percent", [0, 1, 25, 50, 75, 100, 150])
def test_split_sales_never_beat_one_sale(value_cp, value_units, buy_percent):
    thing = _make_pure_item(value_cp, value_units, "Thing", "unit")
    assert_split_sales_never_beat_one_sale(
        thing, 100, buy_percent, [50, 50], [30, 30, 40], [1, 1, 98]
    )


@pytest.mark.story("U129")
@pytest.mark.parametrize("value_cp", [0, 1, 3, 7, 13, 25, 50, 100, 300])
@pytest.mark.parametrize("value_units", [1, 2, 3, 7, 10, 20, 50])
@pytest.mark.parametrize("sell_percent", [0, 1, 25, 50, 75, 100, 150])
@pytest.mark.parametrize("buy_percent", [0, 1, 25, 50, 75, 100])
def test_buy_then_sell_back_never_profits_when_sell_ge_buy(
    value_cp, value_units, sell_percent, buy_percent
):
    if sell_percent < buy_percent:
        pytest.skip("only the sell >= buy case is the profit-free guarantee")
    thing = _make_pure_item(value_cp, value_units, "Thing", "unit")
    for bundle in (1, 5, 13, 50, 100):
        assert_buy_then_sell_back_never_profits(thing, bundle, sell_percent, buy_percent)
