"""Tests for the item value formatting helper."""

import pytest

from items.models import Item
from items.values import NO_VALUE_TEXT, format_item_value

pytestmark = pytest.mark.django_db


def test_format_plain_item_with_value(club):
    """Plain item returns coin format."""
    item = Item.objects.create(club=club, name="Sword", value_cp=1500)  # 15 gp
    result = format_item_value(item)
    assert result == "15 gp"


def test_format_plain_item_with_mixed_coins(club):
    """Plain item with mixed coin values."""
    item = Item.objects.create(club=club, name="Gem", value_cp=1153)  # 11 gp 5 sp 3 cp
    result = format_item_value(item)
    assert result == "11 gp 5 sp 3 cp"


def test_format_plain_item_with_large_value(club):
    """Plain item with large value (uses platinum for >= 10000 gp)."""
    # 10,000 gp = 1,000,000 cp is the threshold for platinum display
    # 1,000,000 cp = 10,000 gp = 1,000 pp
    item = Item.objects.create(club=club, name="Crown", value_cp=1_000_000)
    result = format_item_value(item)
    assert result == "1,000 pp"

    # Below threshold shows in gp
    item2 = Item.objects.create(club=club, name="Gem", value_cp=150_000)  # 1,500 gp
    result2 = format_item_value(item2)
    assert result2 == "1,500 gp"


def test_format_plain_item_zero_value(club):
    """Plain item with zero value returns 'no value'."""
    item = Item.objects.create(club=club, name="Worthless", value_cp=0)
    result = format_item_value(item)
    assert result == NO_VALUE_TEXT


def test_format_stacked_item(club):
    """Stacked item returns 'N gp per <unit>'."""
    item = Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=500,  # 5 gp for 10 sheets
        value_units=10,
    )
    result = format_item_value(item)
    # 500 cp / 10 = 50 cp per sheet = 0 gp per sheet -> "no value"
    assert result == NO_VALUE_TEXT


def test_format_stacked_item_exact_gp(club):
    """Stacked item with exact gp per unit."""
    item = Item.objects.create(
        club=club,
        name="Rope",
        is_stacked=True,
        unit_name="ft",
        value_cp=10000,  # 100 gp for 50 ft
        value_units=50,
    )
    result = format_item_value(item)
    # 10000 / 50 = 200 cp = 2 gp per ft
    assert result == "2 gp per ft"


def test_format_stacked_item_zero_value(club):
    """Stacked item with zero value returns 'no value'."""
    item = Item.objects.create(
        club=club,
        name="Freebie",
        is_stacked=True,
        unit_name="unit",
        value_cp=0,
        value_units=1,
    )
    result = format_item_value(item)
    assert result == NO_VALUE_TEXT


def test_format_stacked_item_fractional_gp(club):
    """Stacked item with fractional gp per unit (integer division)."""
    item = Item.objects.create(
        club=club,
        name="Arrow",
        is_stacked=True,
        unit_name="arrow",
        value_cp=50,  # 50 cp for 20 arrows
        value_units=20,
    )
    result = format_item_value(item)
    # 50 / 20 = 2 cp per arrow = 0 gp per arrow -> "no value"
    assert result == NO_VALUE_TEXT


def test_format_stacked_item_with_silver(club):
    """Stacked item where value per unit is in silver."""
    item = Item.objects.create(
        club=club,
        name="Bolt",
        is_stacked=True,
        unit_name="bolt",
        value_cp=500,  # 500 cp for 5 bolts = 100 cp = 1 gp per bolt
        value_units=5,
    )
    result = format_item_value(item)
    assert result == "1 gp per bolt"


def test_no_value_text_constant():
    """NO_VALUE_TEXT constant is 'no value'."""
    assert NO_VALUE_TEXT == "no value"
