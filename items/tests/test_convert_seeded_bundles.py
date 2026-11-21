"""The convert_seeded_bundles command for existing clubs."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import Membership, User
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import Line, item_quantities, record
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentTemplate,
)

pytestmark = [pytest.mark.django_db]


def run(club, apply=False):
    out = StringIO()
    args = ["convert_seeded_bundles", "--club", club.slug]
    if apply:
        args.append("--apply")
    call_command(*args, stdout=out)
    return out.getvalue()


def make_character(club, name):
    user = User.objects.create_user(f"{name.lower()}@example.com", password="pw", display_name=name)
    membership = Membership.objects.create(user=user, club=club)
    return Character.objects.create(club=club, owner=membership, name=name)


def snapshot():
    return (
        list(Item.objects.order_by("pk").values()),
        LedgerEntry.objects.count(),
    )


@pytest.fixture
def old_arrows(club):
    return Item.objects.create(club=club, name="Arrows (20)", value_cp=100)


@pytest.fixture
def holders(club, old_arrows):
    one, three = make_character(club, "Aria"), make_character(club, "Borin")
    record(one, "award", [Line(item=old_arrows, quantity=1)])
    record(three, "award", [Line(item=old_arrows, quantity=3)])
    return one, three


def test_dry_run_changes_nothing(club, old_arrows, holders):
    before = snapshot()
    out = run(club)
    assert "DRY RUN" in out
    assert snapshot() == before
    old_arrows.refresh_from_db()
    assert old_arrows.name == "Arrows (20)" and not old_arrows.is_stacked


def test_apply_converts_bundles_to_units(club, old_arrows, holders):
    one, three = holders
    run(club, apply=True)
    arrows = Item.objects.get(club=club, name="Arrows")
    assert arrows.pk == old_arrows.pk
    assert arrows.is_stacked and arrows.unit_name == "arrow" and arrows.value_units == 20
    assert arrows.value_cp == 100
    assert item_quantities(one)[arrows.pk] == 20
    assert item_quantities(three)[arrows.pk] == 60
    for char in holders:
        adjustments = LedgerEntry.objects.filter(character=char, kind="adjustment")
        assert adjustments.count() == 1


def test_second_run_changes_nothing(club, old_arrows, holders):
    run(club, apply=True)
    before = snapshot()
    run(club, apply=True)
    assert snapshot() == before


def test_holding_both_plain_and_bundle_refuses(club, old_arrows):
    bolt = Item.objects.create(club=club, name="Crossbow Bolt", value_cp=1)
    bundle = Item.objects.create(club=club, name="Crossbow Bolts (20)", value_cp=100)
    char = make_character(club, "Cora")
    record(char, "award", [Line(item=bolt, quantity=5), Line(item=bundle, quantity=1)])
    before = snapshot()
    with pytest.raises(CommandError):
        run(club, apply=True)
    assert snapshot() == before  # nothing was written


def test_refusal_message_names_character(club):
    bolt = Item.objects.create(club=club, name="Crossbow Bolt", value_cp=1)
    bundle = Item.objects.create(club=club, name="Crossbow Bolts (20)", value_cp=100)
    char = make_character(club, "Cora")
    record(char, "award", [Line(item=bolt, quantity=5), Line(item=bundle, quantity=1)])
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("convert_seeded_bundles", "--club", club.slug, stdout=out)
    assert "hold both" in out.getvalue() and "Cora" in out.getvalue()


def test_plain_bolts_merge_one_to_one_with_bundle_item(club):
    bolt = Item.objects.create(club=club, name="Crossbow Bolt", value_cp=1)
    bundle = Item.objects.create(club=club, name="Crossbow Bolts (20)", value_cp=100)
    plain_holder = make_character(club, "Cora")
    bundle_holder = make_character(club, "Dax")
    record(plain_holder, "award", [Line(item=bolt, quantity=20)])
    record(bundle_holder, "award", [Line(item=bundle, quantity=2)])

    # dry run works on the main case and writes nothing
    before = snapshot()
    run(club)
    assert snapshot() == before

    run(club, apply=True)
    bolts = Item.objects.get(club=club, name="Crossbow Bolts")
    assert bolts.pk == bundle.pk
    assert item_quantities(plain_holder)[bolts.pk] == 20  # 1:1, not 20 x 20
    assert item_quantities(bundle_holder)[bolts.pk] == 40
    bolt.refresh_from_db()
    assert bolt.retired
    assert item_quantities(plain_holder).get(bolt.pk, 0) == 0

    before = snapshot()
    run(club, apply=True)
    assert snapshot() == before


def test_plain_item_without_bundle_item_becomes_stacked(club):
    arrow = Item.objects.create(club=club, name="Arrow", value_cp=1)
    char = make_character(club, "Eve")
    record(char, "award", [Line(item=arrow, quantity=20)])
    run(club, apply=True)
    arrow.refresh_from_db()
    assert arrow.name == "Arrows"
    assert arrow.is_stacked and arrow.unit_name == "arrow"
    assert arrow.value_units == 20 and arrow.value_cp == 100
    assert item_quantities(char)[arrow.pk] == 20


def test_target_name_already_taken_refuses(club, old_arrows):
    Item.objects.create(
        club=club, name="Arrows", value_cp=100, is_stacked=True, unit_name="arrow", value_units=20
    )
    with pytest.raises(CommandError):
        run(club, apply=True)
    old_arrows.refresh_from_db()
    assert old_arrows.name == "Arrows (20)"


def test_starting_equipment_lines_are_repointed_and_scaled(club, old_arrows, character_class):
    template = StartingEquipmentTemplate.objects.create(club=club, name="T", is_active=True)
    entry = StartingEquipmentClassEntry.objects.create(
        template=template, class_option=character_class, min_level=1, max_level=20, coins_cp=0
    )
    bolt = Item.objects.create(club=club, name="Crossbow Bolt", value_cp=1)
    bundle = Item.objects.create(club=club, name="Crossbow Bolts (20)", value_cp=100)
    StartingEquipmentClassLine.objects.create(class_entry=entry, item=old_arrows, quantity=1)
    StartingEquipmentClassLine.objects.create(class_entry=entry, item=bundle, quantity=1)
    StartingEquipmentClassLine.objects.create(class_entry=entry, item=bolt, quantity=20)
    run(club, apply=True)
    lines = {line.item.name: line.quantity for line in StartingEquipmentClassLine.objects.all()}
    # bundle line x1 -> 20 units; plain 20 bolts fold into the same line (1:1)
    assert lines == {"Arrows": 20, "Crossbow Bolts": 40}


@pytest.fixture
def character_class(club):
    from character_options.models import CharacterClass

    return CharacterClass.objects.create(club=club, name="Fighter")


def test_caltrops_assumption_is_stated(club):
    out = run(club)
    assert "Caltrops" in out and "one bag/bundle" in out
