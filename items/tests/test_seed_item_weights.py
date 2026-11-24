"""The seed_item_weights catch-up command (story U154 seeding)."""

from io import StringIO

import pytest
from django.core.management import call_command

from accounts.club_seeding import seed_new_club
from items.models import Item
from shops.gear import GENERAL_STORE_GEAR
from starting_equipment.seeding import STARTING_EQUIPMENT_WEIGHTS

pytestmark = [pytest.mark.django_db]


def run(club, apply=False):
    out = StringIO()
    args = ["seed_item_weights", "--club", club.slug]
    if apply:
        args.append("--apply")
    call_command(*args, stdout=out)
    return out.getvalue()


def weights(club):
    """{name: weight_hundredth_lb} for every item in the club."""
    return {
        row["name"]: row["weight_hundredth_lb"]
        for row in Item.objects.filter(club=club)
        .order_by("name")
        .values("name", "weight_hundredth_lb")
    }


def seeded_names_with_weights():
    """All seeded names that carry a weight (gear + starting equipment)."""
    names = {gear.name for gear in GENERAL_STORE_GEAR if gear.weight_lb is not None}
    names |= {name for name, lb in STARTING_EQUIPMENT_WEIGHTS.items() if lb is not None}
    return names


def test_dry_run_writes_nothing(club):
    """A dry run reports what it would do but writes nothing to the DB."""
    Item.objects.create(club=club, name="Rope", value_cp=100)
    Item.objects.create(club=club, name="Leather Armor", value_cp=1000)
    Item.objects.create(club=club, name="Odd Thing", value_cp=100)

    before = weights(club)
    out = run(club)

    assert "DRY RUN" in out
    assert weights(club) == before
    assert "not in club, skipping" in out


def test_apply_fills_blanks_only_for_seeded_names(club):
    """Apply fills blank weights for seeded names and leaves everything else."""
    Item.objects.create(club=club, name="Rope", value_cp=100)
    Item.objects.create(club=club, name="Leather Armor", value_cp=1000)
    Item.objects.create(club=club, name="Odd Thing", value_cp=100)

    out = run(club, apply=True)

    assert weights(club) == {"Rope": 500, "Leather Armor": 500, "Odd Thing": None}
    assert "weight set to 5.00 lb" in out
    assert "Odd Thing" not in out


def test_never_overwrites_admin_weight(club):
    """A weight an admin set is never overwritten."""
    Item.objects.create(club=club, name="Rope", value_cp=100, weight_hundredth_lb=999)
    Item.objects.create(club=club, name="Torch", value_cp=1, weight_hundredth_lb=123)

    before = weights(club)
    out = run(club, apply=True)

    assert weights(club) == before
    assert "not overwritten" in out
    assert "weight set to" not in out


def test_second_run_does_nothing(club):
    """A second apply run fills nothing (idempotent)."""
    Item.objects.create(club=club, name="Rope", value_cp=100)

    run(club, apply=True)
    before = weights(club)
    out = run(club, apply=True)

    assert weights(club) == before
    assert "Weights filled: 0" in out


def test_new_clubs_seed_with_weights(club):
    """New clubs seed General Store and starting-equipment items with weights.

    Items created by pack seeding (which runs first) keep their blank weight;
    general-store-only and starting-equipment items are born with a weight.
    """
    seed_new_club(club)

    w = weights(club)
    assert w["Rope"] == 500  # 5 lb, general-store-only
    assert w["Sack"] == 50  # 0.5 lb, general-store-only
    assert w["Acid"] == 100  # 1 lb, general-store-only
    assert w["Chain"] == 1000  # 10 lb, general-store-only
    assert w["Arrows"] == 5  # 0.05 lb per arrow (stacked)
    assert w["Leather Armor"] == 500  # starting equipment, 5 lb
    assert w["Longsword"] == 400  # starting equipment, 4 lb
    assert w["Thieves' Tools"] == 100  # starting equipment, 1 lb
    # Items with no listed SRD weight stay blank
    assert w["Antitoxin"] is None
    assert w["Mirror"] is None
    # Pack content items are created blank by pack seeding (which runs first)
    # and are not overwritten; the catch-up command backfills them later.
    assert w["Torch"] is None
    assert w["Backpack"] is None


def test_all_seeded_weight_names_are_known(club):
    """Sanity check: every name the command would touch is a seeded name."""
    names = seeded_names_with_weights()
    gear_names = {gear.name for gear in GENERAL_STORE_GEAR}
    se_names = set(STARTING_EQUIPMENT_WEIGHTS)
    assert names <= gear_names | se_names
