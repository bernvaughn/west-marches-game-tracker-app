"""Unit tests for the stacked-item pricing and label helpers (U123-U131).

Pure functions, no database. Stacked items are built with ``SimpleNamespace``
so the tests exercise ``items/stacked.py`` in isolation; factory-based cases
use the real DB fixtures from ``items/tests/factories.py``.
"""

from fractions import Fraction
from types import SimpleNamespace

import pytest

from items.services import StackedPricingService
from items.tests.factories import make_arrows, make_rope
from tests.property_tests import (  # noqa: F401
    test_buy_then_sell_back_never_profits_when_sell_ge_buy,  # noqa: F401
    test_split_sales_never_beat_one_sale,  # noqa: F401
)


def item(value_cp, value_units, name="Thing", unit_name="unit", stacked=True):
    """Build a pure stand-in item with the fields ``stacked.py`` reads."""
    return SimpleNamespace(
        name=name,
        unit_name=unit_name,
        value_cp=value_cp,
        value_units=value_units,
        is_stacked=stacked,
    )


# --- spec values (pure, no DB) --------------------------------------------


@pytest.mark.story("U125")
def test_rope_bundle_of_50_at_100_percent_is_100_cp():
    rope = item(100, 50, "Rope", "ft")
    assert StackedPricingService.bundle_price(rope, 50, 100) == 100


@pytest.mark.story("U125")
def test_rope_bundle_of_10_at_100_percent_is_20_cp():
    rope = item(100, 50, "Rope", "ft")
    assert StackedPricingService.bundle_price(rope, 10, 100) == 20


@pytest.mark.story("U125")
def test_arrows_bundle_of_5_at_100_percent_is_25_cp():
    arrows = item(100, 20, "Arrows", "arrow")
    assert StackedPricingService.bundle_price(arrows, 5, 100) == 25


@pytest.mark.story("U126")
def test_parchment_one_sheet_at_100_percent_is_10_cp():
    parchment = item(100, 10, "Parchment", "sheet")
    assert StackedPricingService.bundle_price(parchment, 1, 100) == 10


@pytest.mark.story("U129")
def test_sell_one_parchment_sheet_at_100_percent_is_10_cp():
    parchment = item(100, 10, "Parchment", "sheet")
    assert StackedPricingService.sale_price(parchment, 1, 100) == 10


# --- factory-based spec values (DB) --------------------------------------


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_factory_rope_bundle_of_50_at_100_percent_is_100_cp(db, club):
    rope = make_rope(club)
    assert StackedPricingService.bundle_price(rope, 50, 100) == 100


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_factory_arrows_bundle_of_5_at_100_percent_is_25_cp(db, club):
    arrows = make_arrows(club)
    assert StackedPricingService.bundle_price(arrows, 5, 100) == 25


# --- never round per unit -------------------------------------------------


@pytest.mark.story("U129")
def test_selling_in_pieces_never_beats_selling_all_at_once():
    arrows = item(100, 20, "Arrows", "arrow")
    # 1 arrow at 50% buy: floor(100*1*50/(100*20)) = floor(2.5) = 2
    assert StackedPricingService.sale_price(arrows, 1, 50) == 2
    # 7 arrows at 50% buy: floor(100*7*50/(100*20)) = floor(17.5) = 17
    assert StackedPricingService.sale_price(arrows, 7, 50) == 17
    # Per-unit rounding would give 7 * 2 = 14, never the 17 for the whole.
    assert StackedPricingService.sale_price(arrows, 7, 50) >= 7 * StackedPricingService.sale_price(
        arrows, 1, 50
    )


# --- property: buy then sell back can profit when sell < buy --------------


@pytest.mark.story("U129")
def test_buy_then_sell_back_can_profit_when_sell_lt_buy():
    """sell_pct < buy_pct breaks the guarantee: the condition matters."""
    thing = item(100, 10, "Parchment", "sheet")
    cost = StackedPricingService.bundle_price(thing, 10, 50)  # ceil(100*10*50/(100*10)) = 50
    revenue = StackedPricingService.sale_price(thing, 10, 100)  # floor(100*10*100/(100*10)) = 100
    assert revenue > cost


# --- integer-only math -----------------------------------------------------


@pytest.mark.story("U123")
def test_results_are_ints_never_floats():
    rope = item(100, 50, "Rope", "ft")
    assert type(StackedPricingService.bundle_price(rope, 10, 100)) is int
    assert type(StackedPricingService.sale_price(rope, 7, 50)) is int


@pytest.mark.story("U123")
def test_large_values_match_exact_fraction_math():
    rope = item(10**12, 50, "Rope", "ft")
    expected = -(-(10**12 * 10 * 100) // (100 * 50))
    assert StackedPricingService.bundle_price(rope, 10, 100) == expected
    # ceil(a/b) == -(-a//b); compare against Fraction ceiling
    exact = Fraction(10**12 * 10 * 100, 100 * 50)
    assert StackedPricingService.bundle_price(rope, 10, 100) == -(
        -exact.numerator // exact.denominator
    )
    assert StackedPricingService.sale_price(rope, 7, 50) == (10**12 * 7 * 50) // (100 * 50)


# --- validation ------------------------------------------------------------


@pytest.mark.story("U123")
@pytest.mark.parametrize(
    "fn, kwargs",
    [
        (StackedPricingService.bundle_price, {"bundle_units": 0, "sell_percent": 100}),
        (StackedPricingService.bundle_price, {"bundle_units": -1, "sell_percent": 100}),
        (StackedPricingService.bundle_price, {"bundle_units": 5, "sell_percent": -1}),
        (StackedPricingService.bundle_price, {"bundle_units": 5, "sell_percent": True}),
        (StackedPricingService.bundle_price, {"bundle_units": 5, "sell_percent": 50.0}),
        (StackedPricingService.sale_price, {"units": 0, "buy_percent": 100}),
        (StackedPricingService.sale_price, {"units": -3, "buy_percent": 100}),
        (StackedPricingService.sale_price, {"units": 5, "buy_percent": -1}),
        (StackedPricingService.sale_price, {"units": 5, "buy_percent": False}),
        (StackedPricingService.sale_price, {"units": 5, "buy_percent": 50.0}),
    ],
)
def test_bad_units_or_negative_percent_raise(fn, kwargs):
    thing = item(100, 10, "Thing", "unit")
    with pytest.raises(ValueError):
        fn(thing, **kwargs)


@pytest.mark.story("U129")
@pytest.mark.parametrize("n", [1, 7, 100])
def test_zero_percent_prices_to_zero(n):
    """0% is valid shop data (manage form allows 0-1000); it prices to 0."""
    rope = item(100, 50, "Rope", "ft")
    assert StackedPricingService.sale_price(rope, n, 0) == 0
    assert StackedPricingService.bundle_price(rope, n, 0) == 0


# --- labels ----------------------------------------------------------------


@pytest.mark.story("U127")
def test_unit_label_stacked():
    rope = item(100, 50, "Rope", "ft")
    assert StackedPricingService.unit_label(rope, 40) == "40 ft Rope"


@pytest.mark.story("U127")
def test_unit_label_one_sheet_parchment():
    parchment = item(100, 10, "Parchment", "sheet")
    assert StackedPricingService.unit_label(parchment, 1) == "1 sheet Parchment"


@pytest.mark.story("U127")
def test_unit_label_many_arrows():
    arrows = item(100, 20, "Arrows", "arrow")
    assert StackedPricingService.unit_label(arrows, 105) == "105 arrow Arrows"


@pytest.mark.story("U127")
def test_unit_label_normal_item():
    rope = item(100, 1, "Rope", "ft", stacked=False)
    assert StackedPricingService.unit_label(rope, 3) == "3 × Rope"


@pytest.mark.story("U125")
def test_bundle_label_stacked():
    arrows = item(100, 20, "Arrows", "arrow")
    assert StackedPricingService.bundle_label(arrows, 100) == "bundle of 100 arrow"


@pytest.mark.story("U125")
def test_bundle_label_normal_item_returns_name():
    rope = item(100, 1, "Rope", "ft", stacked=False)
    assert StackedPricingService.bundle_label(rope, 1) == "Rope"
