"""Tests for the weight column in the item catalogue (U166)."""

import pytest
from django.urls import reverse

from items.models import Item

pytestmark = [pytest.mark.story("I166"), pytest.mark.django_db]


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def form(**kw):
    return {
        "name": "Test Item",
        "description": "",
        "traits": "",
        "details": "",
        "value_pp": "",
        "value_gp": "",
        "value_sp": "",
        "value_cp": "",
        **kw,
    }


@pytest.fixture
def weighted_items(club, club_admin):
    """Create items with various weights."""
    # Lightest
    light = Item.objects.create(club=club, name="Feather", weight_hundredth_lb=5, value_cp=10)
    # Medium
    medium = Item.objects.create(club=club, name="Sword", weight_hundredth_lb=300, value_cp=1500)
    # Heaviest
    heavy = Item.objects.create(club=club, name="Anvil", weight_hundredth_lb=2000, value_cp=5000)
    # No weight listed
    no_weight = Item.objects.create(club=club, name="Ghost", value_cp=100)
    return light, medium, heavy, no_weight


def test_weight_column_shows_formatted_weight(login, player, club, weighted_items):
    light, medium, heavy, no_weight = weighted_items
    c = login(player)
    r = c.get(url("index", club))
    content = r.content.decode()
    # Should show formatted weight like "0.1 lb" or "3.0 lb"
    assert "0.1 lb" in content  # 5 hundredths = 0.05 lb, rounds to 0.1 lb
    assert "3.0 lb" in content  # 300 hundredths = 3.0 lb
    assert "20.0 lb" in content  # 2000 hundredths = 20.0 lb


def test_weight_column_shows_dash_for_not_listed(login, player, club, weighted_items):
    light, medium, heavy, no_weight = weighted_items
    c = login(player)
    r = c.get(url("index", club))
    content = r.content.decode()
    # No weight listed should show em dash
    assert "—" in content


def test_sort_weight_ascending_puts_lightest_first(login, club_admin, club, weighted_items):
    light, medium, heavy, no_weight = weighted_items
    c = login(club_admin)
    r = c.get(url("index", club) + "?weight=asc")
    content = r.content.decode()
    # Order should be: Feather (0.05), Sword (3.0), Anvil (20.0), Ghost (—)
    feather_pos = content.index("Feather")
    sword_pos = content.index("Sword")
    anvil_pos = content.index("Anvil")
    ghost_pos = content.index("Ghost")
    assert feather_pos < sword_pos < anvil_pos < ghost_pos


def test_sort_weight_descending_puts_heaviest_first(login, club_admin, club, weighted_items):
    light, medium, heavy, no_weight = weighted_items
    c = login(club_admin)
    r = c.get(url("index", club) + "?weight=desc")
    content = r.content.decode()
    # Order should be: Anvil (20.0), Sword (3.0), Feather (0.05), Ghost (—)
    anvil_pos = content.index("Anvil")
    sword_pos = content.index("Sword")
    feather_pos = content.index("Feather")
    ghost_pos = content.index("Ghost")
    assert anvil_pos < sword_pos < feather_pos < ghost_pos


def test_no_weight_listed_filter_alone(login, club_admin, club, weighted_items):
    light, medium, heavy, no_weight = weighted_items
    c = login(club_admin)
    r = c.get(url("index", club) + "?no_weight=1")
    content = r.content.decode()
    # Should only show Ghost (no weight listed)
    assert "Ghost" in content
    assert "Feather" not in content
    assert "Sword" not in content
    assert "Anvil" not in content


def test_no_weight_listed_filter_with_magic_type(login, club_admin, club, weighted_items):
    light, medium, heavy, no_weight = weighted_items
    # Give some items a magic type
    light.magic_type = "weapon"
    light.save()
    no_weight.magic_type = "weapon"
    no_weight.save()
    c = login(club_admin)
    r = c.get(url("index", club) + "?magic_type=weapon&no_weight=1")
    content = r.content.decode()
    # Should only show Ghost (magic_type=weapon AND no weight)
    assert "Ghost" in content
    assert "Feather" not in content


def test_club_scoping_items_of_other_club_never_appear(
    login, club_admin, club, other_club, weighted_items
):
    light, medium, heavy, no_weight = weighted_items
    # Create an item in another club
    Item.objects.create(club=other_club, name="Foreign Item", weight_hundredth_lb=100)
    c = login(club_admin)
    r = c.get(url("index", club))
    content = r.content.decode()
    assert "Foreign Item" not in content
    # Also test with filters
    r = c.get(url("index", club) + "?no_weight=1")
    content = r.content.decode()
    assert "Foreign Item" not in content
    r = c.get(url("index", club) + "?weight=asc")
    content = r.content.decode()
    assert "Foreign Item" not in content


def test_weight_sort_toggle_cycles_off_asc_desc(login, club_admin, club, weighted_items):
    light, medium, heavy, no_weight = weighted_items
    c = login(club_admin)
    # Off (default)
    r = c.get(url("index", club))
    content = r.content.decode()
    # Should have weight=asc in the header link
    assert "weight=asc" in content
    # Asc
    r = c.get(url("index", club) + "?weight=asc")
    content = r.content.decode()
    assert "weight=desc" in content
    # Desc
    r = c.get(url("index", club) + "?weight=desc")
    content = r.content.decode()
    # Link should go to off (no weight param)
    assert "weight=" not in content


def test_sort_stability_preserves_name_order_for_ties(login, club_admin, club):
    """Items with same weight should keep name order from queryset."""
    Item.objects.create(club=club, name="Aardvark", weight_hundredth_lb=100)
    Item.objects.create(club=club, name="Zebra", weight_hundredth_lb=100)
    Item.objects.create(club=club, name="Middle", weight_hundredth_lb=100)
    c = login(club_admin)
    r = c.get(url("index", club) + "?weight=asc")
    content = r.content.decode()
    aardvark_pos = content.index("Aardvark")
    middle_pos = content.index("Middle")
    zebra_pos = content.index("Zebra")
    assert aardvark_pos < middle_pos < zebra_pos
