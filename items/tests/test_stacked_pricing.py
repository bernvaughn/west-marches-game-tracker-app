"""Unit tests for the stacked-item pricing and label helpers (U123-U131).

Pure functions, no database. Stacked items are built with ``SimpleNamespace``
so the tests exercise ``items/stacked.py`` in isolation; factory-based cases
use the real DB fixtures from ``items/tests/factories.py``.
"""

from fractions import Fraction
from types import SimpleNamespace

import pytest

from items.stacked import bundle_label, bundle_price, sale_price, unit_label
from items.tests.factories import make_arrows, make_rope


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
    assert bundle_price(rope, 50, 100) == 100


@pytest.mark.story("U125")
def test_rope_bundle_of_10_at_100_percent_is_20_cp():
    rope = item(100, 50, "Rope", "ft")
    assert bundle_price(rope, 10, 100) == 20


@pytest.mark.story("U125")
def test_arrows_bundle_of_5_at_100_percent_is_25_cp():
    arrows = item(100, 20, "Arrows", "arrow")
    assert bundle_price(arrows, 5, 100) == 25


@pytest.mark.story("U126")
def test_parchment_one_sheet_at_100_percent_is_10_cp():
    parchment = item(100, 10, "Parchment", "sheet")
    assert bundle_price(parchment, 1, 100) == 10


@pytest.mark.story("U129")
def test_sell_one_parchment_sheet_at_100_percent_is_10_cp():
    parchment = item(100, 10, "Parchment", "sheet")
    assert sale_price(parchment, 1, 100) == 10


# --- factory-based spec values (DB) --------------------------------------


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_factory_rope_bundle_of_50_at_100_percent_is_100_cp(db, club):
    rope = make_rope(club)
    assert bundle_price(rope, 50, 100) == 100


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_factory_arrows_bundle_of_5_at_100_percent_is_25_cp(db, club):
    arrows = make_arrows(club)
    assert bundle_price(arrows, 5, 100) == 25


# --- never round per unit -------------------------------------------------


@pytest.mark.story("U129")
def test_selling_in_pieces_never_beats_selling_all_at_once():
    arrows = item(100, 20, "Arrows", "arrow")
    # 1 arrow at 50% buy: floor(100*1*50/(100*20)) = floor(2.5) = 2
    assert sale_price(arrows, 1, 50) == 2
    # 7 arrows at 50% buy: floor(100*7*50/(100*20)) = floor(17.5) = 17
    assert sale_price(arrows, 7, 50) == 17
    # Per-unit rounding would give 7 * 2 = 14, never the 17 for the whole.
    assert sale_price(arrows, 7, 50) >= 7 * sale_price(arrows, 1, 50)


# --- property: split sales never beat one sale ----------------------------


def _split_sale_total(it, units, buy_percent, parts):
    return sum(sale_price(it, p, buy_percent) for p in parts if p >= 1)


@pytest.mark.story("U129")
@pytest.mark.parametrize("value_cp", [0, 1, 3, 7, 13, 25, 50, 100, 300])
@pytest.mark.parametrize("value_units", [1, 2, 3, 7, 10, 20, 50])
@pytest.mark.parametrize("buy_percent", [1, 25, 50, 75, 100, 150])
def test_split_sales_never_beat_one_sale(value_cp, value_units, buy_percent):
    thing = item(value_cp, value_units, "Thing", "unit")
    total = sale_price(thing, 100, buy_percent)
    # two-way and three-way splits
    assert _split_sale_total(thing, 100, buy_percent, [50, 50]) <= total
    assert _split_sale_total(thing, 100, buy_percent, [30, 30, 40]) <= total
    assert _split_sale_total(thing, 100, buy_percent, [1, 1, 98]) <= total


# --- property: buy then sell back never profits ---------------------------


@pytest.mark.story("U129")
@pytest.mark.parametrize("value_cp", [0, 1, 3, 7, 13, 25, 50, 100, 300])
@pytest.mark.parametrize("value_units", [1, 2, 3, 7, 10, 20, 50])
@pytest.mark.parametrize("sell_percent", [1, 25, 50, 75, 100, 150])
@pytest.mark.parametrize("buy_percent", [1, 25, 50, 75, 100])
def test_buy_then_sell_back_never_profits_when_sell_ge_buy(
    value_cp, value_units, sell_percent, buy_percent
):
    if sell_percent < buy_percent:
        pytest.skip("only the sell >= buy case is the profit-free guarantee")
    thing = item(value_cp, value_units, "Thing", "unit")
    for bundle in (1, 5, 13, 50, 100):
        cost = bundle_price(thing, bundle, sell_percent)
        revenue = sale_price(thing, bundle, buy_percent)
        assert revenue <= cost, (
            f"profit: buy {bundle} for {cost} cp, sell back for {revenue} cp "
            f"(sell {sell_percent}% >= buy {buy_percent}%)"
        )


@pytest.mark.story("U129")
def test_buy_then_sell_back_can_profit_when_sell_lt_buy():
    """sell_pct < buy_pct breaks the guarantee: the condition matters."""
    thing = item(100, 10, "Parchment", "sheet")
    cost = bundle_price(thing, 10, 50)  # ceil(100*10*50/(100*10)) = 50
    revenue = sale_price(thing, 10, 100)  # floor(100*10*100/(100*10)) = 100
    assert revenue > cost


# --- integer-only math -----------------------------------------------------


@pytest.mark.story("U123")
def test_results_are_ints_never_floats():
    rope = item(100, 50, "Rope", "ft")
    assert type(bundle_price(rope, 10, 100)) is int
    assert type(sale_price(rope, 7, 50)) is int


@pytest.mark.story("U123")
def test_large_values_match_exact_fraction_math():
    rope = item(10**12, 50, "Rope", "ft")
    expected = -(-(10**12 * 10 * 100) // (100 * 50))
    assert bundle_price(rope, 10, 100) == expected
    # ceil(a/b) == -(-a//b); compare against Fraction ceiling
    exact = Fraction(10**12 * 10 * 100, 100 * 50)
    assert bundle_price(rope, 10, 100) == -(-exact.numerator // exact.denominator)
    assert sale_price(rope, 7, 50) == (10**12 * 7 * 50) // (100 * 50)


# --- validation ------------------------------------------------------------


@pytest.mark.story("U123")
@pytest.mark.parametrize(
    "fn, kwargs",
    [
        (bundle_price, {"bundle_units": 0, "sell_percent": 100}),
        (bundle_price, {"bundle_units": 5, "sell_percent": 0}),
        (sale_price, {"units": 0, "buy_percent": 100}),
        (sale_price, {"units": 5, "buy_percent": 0}),
    ],
)
def test_zero_or_negative_units_raise(fn, kwargs):
    thing = item(100, 10, "Thing", "unit")
    with pytest.raises(ValueError):
        fn(thing, **kwargs)


# --- labels ----------------------------------------------------------------


@pytest.mark.story("U127")
def test_unit_label_stacked():
    rope = item(100, 50, "Rope", "ft")
    assert unit_label(rope, 40) == "40 ft Rope"


@pytest.mark.story("U127")
def test_unit_label_one_sheet_parchment():
    parchment = item(100, 10, "Parchment", "sheet")
    assert unit_label(parchment, 1) == "1 sheet Parchment"


@pytest.mark.story("U127")
def test_unit_label_many_arrows():
    arrows = item(100, 20, "Arrows", "arrow")
    assert unit_label(arrows, 105) == "105 arrow Arrows"


@pytest.mark.story("U127")
def test_unit_label_normal_item():
    rope = item(100, 1, "Rope", "ft", stacked=False)
    assert unit_label(rope, 3) == "3 × Rope"


@pytest.mark.story("U125")
def test_bundle_label_stacked():
    arrows = item(100, 20, "Arrows", "arrow")
    assert bundle_label(arrows, 100) == "bundle of 100 arrow"


@pytest.mark.story("U125")
def test_bundle_label_normal_item_returns_name():
    rope = item(100, 1, "Rope", "ft", stacked=False)
    assert bundle_label(rope, 1) == "Rope"
