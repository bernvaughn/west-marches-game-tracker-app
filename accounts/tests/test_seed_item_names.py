"""Pinned counts and renamed names for the seeded club (U153).

Pins the exact seeded item count for a fresh club, every renamed family
from items/seed_names.py (VARIANT_RENAMES), the Diplomat's Pack case
slots, and that no old seeded name survives in a fresh club or the
demo club seeded by ``seed_demo``.
"""

import pytest
from django.core.management import call_command

from accounts.club_seeding import seed_new_club
from accounts.models import Club
from items.models import Item
from items.seed_names import MAP_CASE, OLD_MAP_CASE_NAMES, SCROLL_CASE, VARIANT_RENAMES

pytestmark = [pytest.mark.django_db]

# Every old seeded name that must not survive: the rename table keys plus
# the two map/scroll case spellings (handled outside the table).
OLD_NAMES = set(VARIANT_RENAMES) | set(OLD_MAP_CASE_NAMES)

# The clear "Variant (Kind)" names the seed must contain, plus the two cases.
NEW_NAMES = set(VARIANT_RENAMES.values()) | {MAP_CASE, SCROLL_CASE}


def _fresh_club():
    club = Club.objects.create(name="Fresh Club", slug="fresh-club")
    seed_new_club(club)
    return club


def test_fresh_club_item_count_pinned():
    """A freshly seeded club has exactly 167 catalogue items."""
    club = _fresh_club()
    assert Item.objects.filter(club=club).count() == 167


def test_fresh_club_has_all_renamed_families():
    """Every renamed family is present under its new name in a fresh club."""
    club = _fresh_club()
    present = set(Item.objects.filter(club=club).values_list("name", flat=True))
    missing = sorted(NEW_NAMES - present)
    assert not missing, f"Missing renamed items: {missing}"


def test_fresh_club_has_no_old_names():
    """No old seeded name survives in a freshly seeded club."""
    club = _fresh_club()
    old = Item.objects.filter(club=club, name__in=OLD_NAMES).values_list("name", flat=True)
    assert not old.exists(), f"Old names still present: {list(old)}"


def test_diplomats_pack_case_slots_pinned():
    """Diplomat's Pack: two case slots (positions 1-2), Map/Scroll Case,
    weight 1, qty 1, chance 100, no fixed "Map or Scroll Case" line."""
    club = _fresh_club()
    pack = Item.objects.get(club=club, name="Diplomat's Pack")

    slots = list(pack.slots.order_by("position"))
    assert len(slots) == 12

    for position in (1, 2):
        slot = pack.slots.get(position=position)
        assert slot.chance_pct == 100
        assert slot.unknown is False
        opts = list(slot.options.all())
        assert len(opts) == 2, f"position {position}: expected 2 options"
        names = {o.item.name for o in opts}
        assert names == {MAP_CASE, SCROLL_CASE}
        for o in opts:
            assert o.qty_min == 1 == o.qty_max
            assert o.weight == 1
            assert o.item.value_cp == 100
            assert o.item.symbol in ("🗺️", "📜")

    # No old case spelling anywhere in the club.
    assert not Item.objects.filter(club=club, name__in=OLD_MAP_CASE_NAMES).exists()

    # Fixed neighbours unchanged.
    assert pack.slots.get(position=0).options.get().item.name == "Chest"
    assert pack.slots.get(position=3).options.get().item.name == "Fine Clothes"


def test_demo_club_has_no_old_names():
    """The demo club made by seed_demo contains no old seeded name."""
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    old = Item.objects.filter(club=club, name__in=OLD_NAMES).values_list("name", flat=True)
    assert not old.exists(), f"Old names still present in demo: {list(old)}"
