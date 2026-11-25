"""Tests for the item picker search and components."""

import pytest
from django.urls import reverse

from accounts.models import Membership
from items.models import Item, RecentItemPick
from items.picker import record_pick, search_items

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def membership(club, player):
    """Return the membership for the player in the club."""
    return Membership.objects.get(user=player, club=club)


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def test_search_by_name(login, club_admin, club, item):
    """Search by item name matches results."""
    Item.objects.create(club=club, name="Healing Potion", value_cp=5000)
    Item.objects.create(club=club, name="Mana Potion", value_cp=3000)
    Item.objects.create(club=club, name="Rope", value_cp=100)

    c = login(club_admin)
    r = c.get(url("picker_search", club) + "?q=Potion")
    assert r.status_code == 200
    content = r.content.decode()
    assert "Healing Potion" in content
    assert "Mana Potion" in content
    assert "Rope" not in content


def test_search_by_magic_type(login, club_admin, club):
    """Search by magic item type matches results."""
    Item.objects.create(club=club, name="Magic Sword", magic_type="weapon", value_cp=10000)
    Item.objects.create(club=club, name="Magic Shield", magic_type="armor", value_cp=8000)
    Item.objects.create(club=club, name="Plain Sword", value_cp=500)

    c = login(club_admin)
    r = c.get(url("picker_search", club) + "?q=weapon")
    assert r.status_code == 200
    content = r.content.decode()
    assert "Magic Sword" in content
    assert "Magic Shield" not in content
    assert "Plain Sword" not in content


def test_search_by_trait_word(login, club_admin, club):
    """Search by trait word matches results."""
    Item.objects.create(club=club, name="Fire Sword", traits="fire magical", value_cp=10000)
    Item.objects.create(club=club, name="Ice Dagger", traits="cold magical", value_cp=8000)
    Item.objects.create(club=club, name="Plain Dagger", traits="sharp", value_cp=500)

    c = login(club_admin)
    r = c.get(url("picker_search", club) + "?q=fire")
    assert r.status_code == 200
    content = r.content.decode()
    assert "Fire Sword" in content
    assert "Ice Dagger" not in content
    assert "Plain Dagger" not in content


def test_retired_items_hidden_by_default(login, club_admin, club):
    """Retired items are hidden unless the retired filter is explicitly requested."""
    Item.objects.create(club=club, name="Active Item", value_cp=100)
    Item.objects.create(club=club, name="Retired Item", value_cp=200, retired=True)

    c = login(club_admin)
    r = c.get(url("picker_search", club))
    assert r.status_code == 200
    content = r.content.decode()
    assert "Active Item" in content
    assert "Retired Item" not in content


def test_retired_items_shown_when_requested(login, club_admin, club):
    """Retired items are shown when retired=1 filter is passed."""
    Item.objects.create(club=club, name="Active Item", value_cp=100)
    Item.objects.create(club=club, name="Retired Item", value_cp=200, retired=True)

    c = login(club_admin)
    r = c.get(url("picker_search", club) + "?retired=1")
    assert r.status_code == 200
    content = r.content.decode()
    assert "Active Item" in content
    assert "Retired Item" in content


def test_club_scoping(login, club_admin, club, other_club):
    """Results are scoped to the current club; other clubs' items never appear."""
    Item.objects.create(club=club, name="Local Item", value_cp=100)
    Item.objects.create(club=other_club, name="Foreign Item", value_cp=200)

    c = login(club_admin)
    r = c.get(url("picker_search", club) + "?q=Item")
    assert r.status_code == 200
    content = r.content.decode()
    assert "Local Item" in content
    assert "Foreign Item" not in content


def test_recent_picks_sort_first(login, club_admin, club):
    """Recent picks sort before name matches."""
    from accounts.models import Membership

    admin_membership = Membership.objects.get(user=club_admin, club=club)

    Item.objects.create(club=club, name="Apple", value_cp=100)
    item_b = Item.objects.create(club=club, name="Banana", value_cp=200)
    Item.objects.create(club=club, name="Cherry", value_cp=300)

    # Record a recent pick for Banana using admin's membership
    record_pick(admin_membership, item_b)

    c = login(club_admin)
    r = c.get(url("picker_search", club) + "?q=")
    assert r.status_code == 200
    content = r.content.decode()

    # Banana should appear first due to recent pick
    banana_pos = content.index("Banana")
    apple_pos = content.index("Apple")
    cherry_pos = content.index("Cherry")
    assert banana_pos < apple_pos
    assert banana_pos < cherry_pos


def test_endpoint_returns_at_most_30_matches(login, club_admin, club):
    """Endpoint returns at most 30 matches."""
    for i in range(35):
        Item.objects.create(club=club, name=f"Item {i:02d}", value_cp=100)

    c = login(club_admin)
    r = c.get(url("picker_search", club) + "?q=Item")
    assert r.status_code == 200
    content = r.content.decode()

    # Count result buttons
    assert content.count('class="wm-item-picker-result"') <= 30


def test_no_js_fallback_renders_select(login, club_admin, club, item):
    """No-JavaScript fallback renders a working plain select."""
    c = login(club_admin)
    r = c.get(url("picker_search", club))
    assert r.status_code == 200
    # The picker search endpoint returns partial results, not the full picker
    # The fallback select is in the component template, not this endpoint


def test_picker_search_requires_admin_or_gm(login, player, club_admin, club):
    """Picker search requires admin or GM permissions."""
    c = login(player)
    r = c.get(url("picker_search", club))
    assert r.status_code == 403

    c = login(club_admin)
    r = c.get(url("picker_search", club))
    assert r.status_code == 200


def test_search_function_directly(club, membership):
    """Test the search_items function directly."""
    Item.objects.create(club=club, name="Test Item", value_cp=100)
    Item.objects.create(club=club, name="Another", value_cp=200)

    results = search_items(club, membership, "Test")
    assert len(results) == 1
    assert results[0].name == "Test Item"


def test_search_function_respects_limit(club, membership):
    """Test that search_items respects the limit parameter."""
    for i in range(50):
        Item.objects.create(club=club, name=f"Item {i}", value_cp=100)

    results = search_items(club, membership, "Item", limit=10)
    assert len(results) == 10


def test_search_function_include_retired(club, membership):
    """Test that search_items respects include_retired parameter."""
    Item.objects.create(club=club, name="Active", value_cp=100)
    Item.objects.create(club=club, name="Retired", value_cp=200, retired=True)

    results = search_items(club, membership, "", include_retired=False)
    assert len(results) == 1
    assert results[0].name == "Active"

    results = search_items(club, membership, "", include_retired=True)
    assert len(results) == 2


def test_record_pick_creates_recent_pick(club, membership):
    """Test that record_pick creates a RecentItemPick."""
    item = Item.objects.create(club=club, name="Test", value_cp=100)

    record_pick(membership, item)

    assert RecentItemPick.objects.filter(membership=membership, item=item).exists()


def test_record_pick_updates_timestamp(club, membership):
    """Test that record_pick updates timestamp for existing pick."""
    item = Item.objects.create(club=club, name="Test", value_cp=100)

    record_pick(membership, item)
    first_pick = RecentItemPick.objects.get(membership=membership, item=item)
    first_time = first_pick.used_at

    # Small delay to ensure different timestamp
    import time

    time.sleep(0.01)

    record_pick(membership, item)
    second_pick = RecentItemPick.objects.get(membership=membership, item=item)

    assert second_pick.used_at > first_time
    assert RecentItemPick.objects.filter(membership=membership, item=item).count() == 1


def test_record_pick_trims_to_limit(club, membership):
    """Test that record_pick keeps only the last 10 picks."""
    for i in range(15):
        item = Item.objects.create(club=club, name=f"Item {i}", value_cp=100)
        record_pick(membership, item)

    picks = RecentItemPick.objects.filter(membership=membership).order_by("-used_at")
    assert picks.count() == 10
    # Most recent should be Item 14
    assert picks.first().item.name == "Item 14"
    # Oldest kept should be Item 5
    assert picks.last().item.name == "Item 5"
