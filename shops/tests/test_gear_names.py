"""Tests for the renamed gear list and General Store seeding (U148)."""

import pytest

from items.models import Item
from items.seed_names import MAP_CASE, SCROLL_CASE, VARIANT_RENAMES
from shops.gear import GENERAL_STORE_GEAR
from shops.seeding import seed_default_general_store

pytestmark = pytest.mark.django_db


def test_map_case_and_scroll_case_in_gear_list():
    """Map Case and Scroll Case replace Case, Map or Scroll at 100 cp."""
    by_name = {g.name: g for g in GENERAL_STORE_GEAR}

    assert MAP_CASE in by_name
    assert SCROLL_CASE in by_name
    assert "Case, Map or Scroll" not in by_name

    map_case = by_name[MAP_CASE]
    scroll_case = by_name[SCROLL_CASE]
    assert map_case.value_cp == 100
    assert map_case.icon == "🗺️"
    assert map_case.description == "Holds rolled maps."
    assert scroll_case.value_cp == 100
    assert scroll_case.icon == "📜"
    assert scroll_case.description == "Holds scrolls."


def test_crossbow_bolt_case_unchanged():
    """Case, Crossbow Bolt stays at 100 cp with its icon."""
    by_name = {g.name: g for g in GENERAL_STORE_GEAR}
    bolt = by_name["Case, Crossbow Bolt"]
    assert bolt.value_cp == 100
    assert bolt.icon == "🧰"
    assert bolt.description == ""


def test_focus_and_holy_symbol_rows_renamed():
    """Arcane/Druidic/Holy Symbol rows use the new Variant (Kind) names."""
    names = {g.name for g in GENERAL_STORE_GEAR}

    assert "Crystal (Arcane Focus)" in names
    assert "Orb (Arcane Focus)" in names
    assert "Rod (Arcane Focus)" in names
    assert "Staff (Arcane Focus)" in names
    assert "Wand (Arcane Focus)" in names
    assert "Sprig of Mistletoe (Druidic Focus)" in names
    assert "Staff (Druidic Focus)" in names
    assert "Yew Wand (Druidic Focus)" in names
    assert "Amulet (Holy Symbol)" in names
    assert "Emblem (Holy Symbol)" in names
    assert "Reliquary (Holy Symbol)" in names


def test_no_old_name_remains_in_gear_list():
    """No VARIANT_RENAMES old key remains as a gear name."""
    names = {g.name for g in GENERAL_STORE_GEAR}
    for old in VARIANT_RENAMES:
        assert old not in names, f"{old!r} still in gear list"


def test_gear_names_have_no_duplicates():
    """No duplicate names (casefold) in gear list."""
    names = [g.name.casefold() for g in GENERAL_STORE_GEAR]
    assert len(names) == len(set(names))


def test_seed_creates_both_cases_with_description(club):
    """seed_default_general_store creates Map Case and Scroll Case with description."""
    seed_default_general_store(club)

    map_case = Item.objects.get(club=club, name=MAP_CASE)
    scroll_case = Item.objects.get(club=club, name=SCROLL_CASE)

    assert map_case.value_cp == 100
    assert map_case.symbol == "🗺️"
    assert map_case.description == "Holds rolled maps."
    assert scroll_case.value_cp == 100
    assert scroll_case.symbol == "📜"
    assert scroll_case.description == "Holds scrolls."


def test_seed_leaves_pre_existing_map_case_unchanged(club):
    """Pre-existing Map Case keeps its value and description; not overwritten."""
    Item.objects.create(
        club=club, name=MAP_CASE, value_cp=500, symbol="🗺️", description="Old description"
    )

    seed_default_general_store(club)

    map_case = Item.objects.get(club=club, name=MAP_CASE)
    assert map_case.value_cp == 500
    assert map_case.description == "Old description"


def test_seed_skips_retired_map_case(club):
    """Retired Map Case is not revived; no twin created."""
    Item.objects.create(club=club, name=MAP_CASE, value_cp=100, symbol="🗺️", retired=True)

    seed_default_general_store(club)

    assert Item.objects.filter(club=club, name=MAP_CASE).count() == 1
    assert Item.objects.get(club=club, name=MAP_CASE).retired
