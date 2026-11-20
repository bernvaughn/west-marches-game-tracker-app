"""Tests for the seed_pack_containers management command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from items.containers import roll_container, validate_container_config
from items.models import ContainerSlot, ContainerSlotOption, Item
from ledger.models import LedgerEntry
from ledger.services import Line, record

pytestmark = [pytest.mark.django_db]


def test_seed_command_creates_content_items_slots_and_options(club):
    """Command creates missing content items, sets is_container, builds slots."""
    # Create the pack item but no content items
    pack = Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)

    out = StringIO()
    call_command("seed_pack_containers", "--club", club.slug, stdout=out)

    pack.refresh_from_db()
    assert pack.is_container is True

    slots = list(pack.slots.order_by("position"))
    assert len(slots) == 5

    # Check content items were created
    fine_clothes = Item.objects.get(club=club, name="Fine clothes")
    flask = Item.objects.get(club=club, name="Flask of oil")
    perfume = Item.objects.get(club=club, name="Vial of perfume")
    wax = Item.objects.get(club=club, name="Sealing wax")
    letter = Item.objects.get(club=club, name="Sealed letter")

    # Slot 0: Fine clothes x1
    assert slots[0].chance_pct == 100
    assert slots[0].unknown is False
    opts = list(slots[0].options.all())
    assert len(opts) == 1
    assert opts[0].item == fine_clothes
    assert opts[0].qty_min == 1 and opts[0].qty_max == 1

    # Slot 1: Flask of oil 1-2
    assert slots[1].chance_pct == 100
    opts = list(slots[1].options.all())
    assert opts[0].item == flask
    assert opts[0].qty_min == 1 and opts[0].qty_max == 2

    # Slot 2: Vial of perfume x1
    assert slots[2].chance_pct == 100
    opts = list(slots[2].options.all())
    assert opts[0].item == perfume
    assert opts[0].qty_min == 1 and opts[0].qty_max == 1

    # Slot 3: Sealing wax x1
    assert slots[3].chance_pct == 100
    opts = list(slots[3].options.all())
    assert opts[0].item == wax
    assert opts[0].qty_min == 1 and opts[0].qty_max == 1

    # Slot 4: Sealed letter x1 (in seed data, not unknown)
    assert slots[4].chance_pct == 100
    opts = list(slots[4].options.all())
    assert opts[0].item == letter
    assert opts[0].qty_min == 1 and opts[0].qty_max == 1

    # Validate
    validate_container_config(pack)

    # Roll works
    roll = roll_container(pack)
    assert len(roll.slots) == 5
    for outcome in roll.slots:
        assert outcome.hit is True
        assert outcome.item_id is not None
        assert outcome.qty >= 1

    assert "configured" in out.getvalue()
    assert "Diplomat's Pack" in out.getvalue()


def test_seed_command_idempotent(club):
    """Second run adds no items, slots or options."""
    pack = Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)

    # First run
    out1 = StringIO()
    call_command("seed_pack_containers", "--club", club.slug, stdout=out1)

    item_count_1 = Item.objects.filter(club=club).count()
    slot_count_1 = ContainerSlot.objects.filter(container=pack).count()
    option_count_1 = ContainerSlotOption.objects.filter(slot__container=pack).count()

    # Second run
    out2 = StringIO()
    call_command("seed_pack_containers", "--club", club.slug, stdout=out2)

    item_count_2 = Item.objects.filter(club=club).count()
    slot_count_2 = ContainerSlot.objects.filter(container=pack).count()
    option_count_2 = ContainerSlotOption.objects.filter(slot__container=pack).count()

    assert item_count_2 == item_count_1
    assert slot_count_2 == slot_count_1
    assert option_count_2 == option_count_1
    assert "already configured" in out2.getvalue()


def test_seed_command_reuses_existing_content_items(club):
    """Reuses existing content items by case-insensitive name."""
    Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    # Pre-create one content item
    fine_clothes = Item.objects.create(club=club, name="Fine Clothes", value_cp=999, symbol="👕")
    original_pk = fine_clothes.pk

    call_command("seed_pack_containers", "--club", club.slug)

    # Should reuse the same item (case-insensitive match)
    fine_clothes.refresh_from_db()
    assert fine_clothes.pk == original_pk
    # Value should not be overwritten
    assert fine_clothes.value_cp == 999


def test_seed_command_skips_packs_not_in_catalogue(club):
    """Packs absent from the club are skipped; no pack item created."""
    # Don't create any pack items

    out = StringIO()
    call_command("seed_pack_containers", "--club", club.slug, stdout=out)

    # No items should be created at all
    assert Item.objects.filter(club=club).count() == 0
    assert "not in catalogue" in out.getvalue()


def test_seed_command_does_not_overwrite_admin_edited_pack(club):
    """Pack that already has slots is skipped (admin edits preserved)."""
    pack = Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900, is_container=True)
    # Admin already added a custom slot
    from items.tests.factories import add_slot

    custom_item = Item.objects.create(club=club, name="Custom Item", value_cp=100)
    add_slot(pack, [(custom_item, 5, 5, 1)], chance_pct=50, position=0)

    out = StringIO()
    call_command("seed_pack_containers", "--club", club.slug, stdout=out)

    pack.refresh_from_db()
    slots = list(pack.slots.all())
    # Should still have only the admin's slot
    assert len(slots) == 1
    assert slots[0].chance_pct == 50
    assert slots[0].options.first().item == custom_item
    assert "already configured" in out.getvalue()


def test_seed_command_touches_only_named_club(club, other_club):
    """Items in other clubs are not affected."""
    pack1 = Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    pack2 = Item.objects.create(club=other_club, name="Diplomat's Pack", value_cp=3900)

    call_command("seed_pack_containers", "--club", club.slug)

    pack1.refresh_from_db()
    pack2.refresh_from_db()

    assert pack1.is_container is True
    assert pack1.slots.exists()
    assert pack2.is_container is False
    assert not pack2.slots.exists()


def test_seed_command_no_ledger_writes_keeps_inventory(club, character):
    """Command writes no ledger rows and keeps inventory intact."""
    pack = Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    # Give the character 2 packs via ledger
    record(character=character, kind="award", lines=[Line(item=pack, quantity=2)], note="test")

    ledger_before = LedgerEntry.objects.count()
    # Check inventory via ledger
    from ledger.services import item_quantities

    inv_before = item_quantities(character).get(pack, 0)

    call_command("seed_pack_containers", "--club", club.slug)

    ledger_after = LedgerEntry.objects.count()
    inv_after = item_quantities(character).get(pack, 0)

    assert ledger_after == ledger_before
    assert inv_after == inv_before


def test_seed_command_dry_run_leaves_db_unchanged(club):
    """--dry-run makes no persistent changes."""
    pack = Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)

    out = StringIO()
    call_command("seed_pack_containers", "--club", club.slug, "--dry-run", stdout=out)

    pack.refresh_from_db()
    assert pack.is_container is False
    assert not pack.slots.exists()
    assert Item.objects.filter(club=club, name="Fine clothes").count() == 0
    assert "Rolled back" in out.getvalue() or "Dry run" in out.getvalue()


def test_seed_command_unknown_club_raises_error():
    """Unknown club slug raises CommandError."""
    with pytest.raises(CommandError) as exc:
        call_command("seed_pack_containers", "--club", "nonexistent")
    assert "does not exist" in str(exc.value)


def test_seed_command_missing_club_arg_raises_error():
    """Missing --club argument raises error."""
    with pytest.raises(CommandError) as exc:
        call_command("seed_pack_containers")
    assert "required" in str(exc.value).lower() or "club" in str(exc.value).lower()


def test_seed_command_all_packs_pass_validation(club):
    """Every seeded pack passes validate_container_config."""
    # Create all pack items
    for pack_name in [
        "Diplomat's Pack",
        "Explorer's Pack",
        "Priest's Pack",
        "Dungeoneer's Pack",
        "Burglar's Pack",
        "Scholar's Pack",
        "Entertainer's Pack",
    ]:
        Item.objects.create(club=club, name=pack_name, value_cp=1000)

    call_command("seed_pack_containers", "--club", club.slug)

    for pack_name in [
        "Diplomat's Pack",
        "Explorer's Pack",
        "Priest's Pack",
        "Dungeoneer's Pack",
        "Burglar's Pack",
        "Scholar's Pack",
        "Entertainer's Pack",
    ]:
        pack = Item.objects.get(club=club, name=pack_name)
        validate_container_config(pack)  # Should not raise


def test_seed_command_existing_owner_can_open(club, character):
    """Character who owned the pack before seeding can open it (if open_container exists)."""
    pack = Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900)
    # Give the character 1 pack via ledger
    record(character=character, kind="award", lines=[Line(item=pack, quantity=1)], note="test")

    call_command("seed_pack_containers", "--club", club.slug)

    pack.refresh_from_db()
    assert pack.is_container is True
    assert pack.slots.count() == 5

    # If open_container is available, test it works
    try:
        from items.opening import open_container
    except ImportError:
        pytest.skip("open_container not yet implemented (slice B)")

    opening = open_container(character, pack, character.membership.user)
    assert opening.container == pack
    assert opening.character == character
    assert opening.result  # Has per-slot outcomes
