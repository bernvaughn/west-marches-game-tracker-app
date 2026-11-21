"""Tests for items.unit_notes."""

import pytest

from items.models import Item
from items.unit_notes import with_unit_summary
from ledger.services import Line


@pytest.mark.django_db
def test_with_unit_summary_stacked_items(club):
    """Stacked items add unit summary to note."""
    parchment = Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=100,
        value_units=10,
    )
    rope = Item.objects.create(
        club=club,
        name="Rope",
        is_stacked=True,
        unit_name="ft",
        value_cp=100,
        value_units=50,
    )
    sword = Item.objects.create(
        club=club,
        name="Longsword",
        value_cp=1500,
    )

    lines = [
        Line(item=parchment, quantity=10),
        Line(item=rope, quantity=-3),
        Line(item=sword, quantity=1),
    ]
    result = with_unit_summary("Award for quest", lines)
    assert result == "Award for quest (+10 sheet Parchment, -3 ft Rope)"


@pytest.mark.django_db
def test_with_unit_summary_no_stacked_items(club):
    """Non-stacked items leave note unchanged."""
    sword = Item.objects.create(
        club=club,
        name="Longsword",
        value_cp=1500,
    )
    shield = Item.objects.create(
        club=club,
        name="Shield",
        value_cp=1000,
    )

    lines = [
        Line(item=sword, quantity=1),
        Line(item=shield, quantity=-1),
    ]
    result = with_unit_summary("Award for quest", lines)
    assert result == "Award for quest"


@pytest.mark.django_db
def test_with_unit_summary_empty_note(club):
    """Empty note gets just the summary."""
    parchment = Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=100,
        value_units=10,
    )
    lines = [Line(item=parchment, quantity=5)]
    result = with_unit_summary("", lines)
    assert result == "(+5 sheet Parchment)"


@pytest.mark.django_db
def test_with_unit_summary_only_stacked(club):
    """Note with only stacked items."""
    parchment = Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=100,
        value_units=10,
    )
    lines = [Line(item=parchment, quantity=5)]
    result = with_unit_summary("Gave parchment", lines)
    assert result == "Gave parchment (+5 sheet Parchment)"


@pytest.mark.django_db
def test_with_unit_summary_mixed_positive_negative(club):
    """Positive and negative quantities both get signs."""
    parchment = Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=100,
        value_units=10,
    )
    rope = Item.objects.create(
        club=club,
        name="Rope",
        is_stacked=True,
        unit_name="ft",
        value_cp=100,
        value_units=50,
    )

    lines = [
        Line(item=parchment, quantity=7),
        Line(item=rope, quantity=-2),
    ]
    result = with_unit_summary("Adjusted", lines)
    assert result == "Adjusted (+7 sheet Parchment, -2 ft Rope)"
