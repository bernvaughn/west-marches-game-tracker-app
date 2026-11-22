"""Tests for the Diplomat's Pack and other pack changes (U149, U151)."""

import random
from io import StringIO

import pytest
from django.core.management import call_command

from items.containers import loot_preview, roll_container, validate_container_config
from items.management.commands.seed_pack_containers import PACKS
from items.models import ContainerSlot, ContainerSlotOption, Item
from items.opening import open_container
from items.pack_seeding import seed_pack_containers, slot_options
from ledger.services import Line, available_items, record

pytestmark = [pytest.mark.django_db]


def test_diplomats_pack_has_twelve_slots(club):
    """Diplomat's Pack has 12 slots after seeding."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    seed_pack_containers(club)

    pack = Item.objects.get(club=club, name="Diplomat's Pack")
    slots = list(pack.slots.order_by("position"))
    assert len(slots) == 12


def test_diplomats_pack_case_slots(club):
    """Diplomat's Pack has two case slots at positions 1 and 2 with Map/Scroll Case options."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    seed_pack_containers(club)

    pack = Item.objects.get(club=club, name="Diplomat's Pack")

    # Position 1: first case slot
    case_slot_1 = pack.slots.get(position=1)
    assert case_slot_1.chance_pct == 100
    assert case_slot_1.unknown is False
    opts_1 = list(case_slot_1.options.all())
    assert len(opts_1) == 2
    names_1 = {o.item.name for o in opts_1}
    assert names_1 == {"Map Case", "Scroll Case"}
    for o in opts_1:
        assert o.qty_min == 1 == o.qty_max
        assert o.weight == 1
        assert o.item.value_cp == 100
        assert o.item.symbol in ("🗺️", "📜")

    # Position 2: second case slot
    case_slot_2 = pack.slots.get(position=2)
    assert case_slot_2.chance_pct == 100
    assert case_slot_2.unknown is False
    opts_2 = list(case_slot_2.options.all())
    assert len(opts_2) == 2
    names_2 = {o.item.name for o in opts_2}
    assert names_2 == {"Map Case", "Scroll Case"}
    for o in opts_2:
        assert o.qty_min == 1 == o.qty_max
        assert o.weight == 1
        assert o.item.value_cp == 100

    # No "Map or Scroll Case" item exists
    old_names = ["Map or Scroll Case", "Case, Map or Scroll"]
    assert not Item.objects.filter(club=club, name__in=old_names).exists()

    # Fixed slots unchanged (Chest at 0, Fine Clothes at 3, etc.)
    chest = pack.slots.get(position=0)
    assert chest.options.get().item.name == "Chest"

    fine_clothes = pack.slots.get(position=3)
    assert fine_clothes.options.get().item.name == "Fine Clothes"


def test_diplomats_pack_validates(club):
    """Diplomat's Pack passes validate_container_config."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    seed_pack_containers(club)

    pack = Item.objects.get(club=club, name="Diplomat's Pack")
    validate_container_config(pack)  # Should not raise


def test_diplomats_pack_roll_gives_two_cases(club):
    """Rolling Diplomat's Pack gives exactly two cases (Map + Scroll)."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    seed_pack_containers(club)

    pack = Item.objects.get(club=club, name="Diplomat's Pack")

    # Use seeded random for deterministic results
    rng = random.Random(42)
    # The roll should hit all 12 slots (chance 100)
    roll = roll_container(pack, rng=rng)

    assert len(roll.slots) == 12
    # All slots hit
    for outcome in roll.slots:
        assert outcome.hit is True
        assert outcome.item_id is not None

    # Count case items in the roll
    case_names = ("Map Case", "Scroll Case")
    case_items = [
        o for o in roll.slots if o.item_id and Item.objects.get(pk=o.item_id).name in case_names
    ]
    assert len(case_items) == 2  # Exactly two cases

    # Both Map Case and Scroll Case should appear at least once across multiple rolls
    seen_map = False
    seen_scroll = False
    for _ in range(20):
        rng = random.Random(_)
        roll = roll_container(pack, rng=rng)
        for outcome in roll.slots:
            if outcome.item_id and Item.objects.get(pk=outcome.item_id).name == "Map Case":
                seen_map = True
            if outcome.item_id and Item.objects.get(pk=outcome.item_id).name == "Scroll Case":
                seen_scroll = True
    assert seen_map
    assert seen_scroll


def test_diplomats_pack_loot_preview(club):
    """Loot preview for Diplomat's Pack shows case slots as 'One of' with 50% each."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    seed_pack_containers(club)

    pack = Item.objects.get(club=club, name="Diplomat's Pack")
    preview = loot_preview(pack, viewer_can_see_unknown=True)

    # 12 rows in preview
    assert len(preview) == 12

    # Position 1: first case slot
    row1 = preview[1]
    assert row1.chance_pct == 100
    assert row1.label.startswith("One of")
    assert len(row1.options) == 2
    # Each option at 50%
    for opt in row1.options:
        assert opt.label in ("Map Case", "Scroll Case")
        assert opt.weight_pct == 50  # weight_pct is percentage

    # Position 2: second case slot
    row2 = preview[2]
    assert row2.chance_pct == 100
    assert row2.label.startswith("One of")
    assert len(row2.options) == 2
    for opt in row2.options:
        assert opt.label in ("Map Case", "Scroll Case")
        assert opt.weight_pct == 50

    # Fixed slots unchanged (e.g., Chest at position 0)
    row0 = preview[0]
    assert row0.label == "Chest"
    assert len(row0.options) == 0  # Fixed slots have empty options tuple
    # The single item is in row0.item
    assert row0.item is not None
    assert row0.item.name == "Chest"
    assert row0.qty_min == 1
    assert row0.qty_max == 1


def test_diplomats_pack_open_gives_two_cases(club, character, player):
    """Opening Diplomat's Pack gives exactly 2 cases total."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    seed_pack_containers(club)

    pack = Item.objects.get(club=club, name="Diplomat's Pack")
    # Give character 1 pack
    record(character=character, kind="award", lines=[Line(item=pack, quantity=1)], note="test")

    opening = open_container(character, pack, player)

    assert opening.container == pack
    assert opening.character == character

    # Check result has exactly 2 case items (result is list of dicts with item_id)
    def _is_case(r, name):
        return r.get("item_id") and Item.objects.get(pk=r["item_id"]).name == name

    map_count = sum(1 for r in opening.result if _is_case(r, "Map Case"))
    scroll_count = sum(1 for r in opening.result if _is_case(r, "Scroll Case"))
    total_cases = map_count + scroll_count
    assert total_cases == 2, (
        f"Expected 2 cases, got {total_cases} (Map: {map_count}, Scroll: {scroll_count})"
    )

    # Pack is used up
    held = available_items(character)
    assert held.get(pack.pk, 0) == 0


def test_opened_before_change_keeps_old_result(club, character, player):
    """A pack opened before the change keeps its old result (not rewritten)."""
    # Seed the OLD layout by hand: one fixed slot of 2 "Map or Scroll Case"
    pack = Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900, is_container=True)

    # Create the old content item
    old_case = Item.objects.create(
        club=club, name="Map or Scroll Case", value_cp=100, symbol="📜", retired=False
    )

    # Add one slot with qty 2
    slot = ContainerSlot.objects.create(container=pack, chance_pct=100, unknown=False, position=0)
    ContainerSlotOption.objects.create(slot=slot, item=old_case, qty_min=2, qty_max=2, weight=1)

    # Give character 1 pack and open it
    record(character=character, kind="award", lines=[Line(item=pack, quantity=1)], note="test")
    opening_old = open_container(character, pack, player)

    # Snapshot the opening result
    old_result_snapshot = [(r.get("item_id"), r.get("qty")) for r in opening_old.result]

    # Now delete the slots and re-seed with new layout
    pack.slots.all().delete()
    pack.is_container = False
    pack.save()

    seed_pack_containers(club)

    # The opening result should be unchanged
    # (the opening record is immutable once created)
    opening_old.refresh_from_db()
    new_result_snapshot = [(r.get("item_id"), r.get("qty")) for r in opening_old.result]
    assert new_result_snapshot == old_result_snapshot

    # Character still holds the old item (2x "Map or Scroll Case")
    from ledger.services import item_quantities

    inv = item_quantities(character)
    old_case_id = old_case.pk
    assert inv.get(old_case_id, 0) == 2, f"Expected 2 of old case, got {inv.get(old_case_id, 0)}"


def test_other_packs_unchanged(club):
    """Other packs' slots are byte-for-byte identical to PACKS table."""
    # Create all pack items except Diplomat's
    for pack_name in [
        "Explorer's Pack",
        "Priest's Pack",
        "Dungeoneer's Pack",
        "Burglar's Pack",
        "Scholar's Pack",
        "Entertainer's Pack",
    ]:
        Item.objects.create(club=club, name=pack_name, value_cp=1000)

    call_command("seed_pack_containers", "--club", club.slug, stdout=StringIO())

    for pack_name, contents in PACKS.items():
        if pack_name == "Diplomat's Pack":
            continue
        pack = Item.objects.get(club=club, name=pack_name)
        slots = list(pack.slots.order_by("position"))
        assert len(slots) == len(contents), f"{pack_name}: slot count mismatch"

        for slot, entry in zip(slots, contents, strict=True):
            options = slot_options(entry)
            opts = list(slot.options.all())
            msg = f"{pack_name} pos {slot.position}: option count mismatch"
            assert len(opts) == len(options), msg
            assert slot.chance_pct == 100
            assert slot.unknown is False
            for opt, (name, qty_min, qty_max, _value, _symbol) in zip(opts, options, strict=True):
                assert opt.item.name == name
                assert opt.qty_min == qty_min == qty_max == opt.qty_max
                assert opt.weight == 1


def test_entertainers_pack_lute_renamed(club):
    """Entertainer's Pack holds 'Lute (Musical Instrument)' with value 3500 and symbol 🎵."""
    Item.objects.create(club=club, name="Entertainer's Pack", value_cp=1000)
    seed_pack_containers(club)

    pack = Item.objects.get(club=club, name="Entertainer's Pack")
    lute_slot = pack.slots.get(position=5)
    lute_opt = lute_slot.options.get()

    assert lute_opt.item.name == "Lute (Musical Instrument)"
    assert lute_opt.item.value_cp == 3500
    assert lute_opt.item.symbol == "🎵"
    assert lute_slot.chance_pct == 100
    assert lute_slot.unknown is False

    # No "Instrument (lute)" item or option exists
    assert not Item.objects.filter(club=club, name="Instrument (lute)").exists()


def test_case_items_seeded_at_100_cp(club):
    """Seeded Map Case and Scroll Case have 100 cp and correct symbols."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    seed_pack_containers(club)

    map_case = Item.objects.get(club=club, name="Map Case")
    scroll_case = Item.objects.get(club=club, name="Scroll Case")

    assert map_case.value_cp == 100
    assert map_case.symbol == "🗺️"
    assert scroll_case.value_cp == 100
    assert scroll_case.symbol == "📜"


def test_existing_case_item_reused_not_overwritten(club):
    """An existing 'Map Case' item is reused (value not overwritten)."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    # Pre-create Map Case with different value
    existing_map = Item.objects.create(club=club, name="Map Case", value_cp=999, symbol="🗺️")
    original_pk = existing_map.pk

    seed_pack_containers(club)

    existing_map.refresh_from_db()
    assert existing_map.pk == original_pk
    assert existing_map.value_cp == 999  # Not overwritten


def test_reseeding_idempotent(club):
    """Re-seeding adds no items, slots or options; pack with slots is skipped."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)

    # First run
    out1 = StringIO()
    seed_pack_containers(club, log=out1.write)

    item_count_1 = Item.objects.filter(club=club).count()
    slot_count_1 = ContainerSlot.objects.filter(container__club=club).count()
    option_count_1 = ContainerSlotOption.objects.filter(slot__container__club=club).count()

    # Second run
    out2 = StringIO()
    seed_pack_containers(club, log=out2.write)

    item_count_2 = Item.objects.filter(club=club).count()
    slot_count_2 = ContainerSlot.objects.filter(container__club=club).count()
    option_count_2 = ContainerSlotOption.objects.filter(slot__container__club=club).count()

    assert item_count_2 == item_count_1
    assert slot_count_2 == slot_count_1
    assert option_count_2 == option_count_1
    assert "already configured" in out2.getvalue()


def test_management_command_diplomats_pack(club):
    """Management command works for Diplomat's Pack with new layout."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)

    out = StringIO()
    call_command("seed_pack_containers", "--club", club.slug, stdout=out)

    pack = Item.objects.get(club=club, name="Diplomat's Pack")
    assert pack.slots.count() == 12
    assert "configured" in out.getvalue()
