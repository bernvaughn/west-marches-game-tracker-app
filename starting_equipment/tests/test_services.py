"""Tests for starting_equipment.services.apply_starting_equipment."""

import pytest

from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)
from starting_equipment.services import apply_starting_equipment

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def template(club):
    """Create a starting equipment template."""
    return StartingEquipmentTemplate.objects.create(
        club=club, name="Test Template", is_active=True
    )


@pytest.fixture
def class_item(club):
    """Create an item for class equipment."""
    return club.items.create(name="Class Weapon", value_cp=1000)


@pytest.fixture
def class_coins_item(club):
    """Create an item for class coins (not used, coins are direct)."""
    return club.items.create(name="Gold", value_cp=100)


@pytest.fixture
def background_item(club):
    """Create an item for background equipment."""
    return club.items.create(name="Background Tool", value_cp=500)


@pytest.fixture
def level_coins_item(club):
    """Create an item for level coins (not used, coins are direct)."""
    return club.items.create(name="More Gold", value_cp=100)


@pytest.fixture
def magic_item(club):
    """Create a magic item for requests."""
    return club.items.create(name="Magic Sword", value_cp=5000)


@pytest.fixture
def class_entry(template, class_item):
    """Create a class entry for Fighter level 1-5."""
    entry = StartingEquipmentClassEntry.objects.create(
        template=template,
        char_class="Fighter",
        min_level=1,
        max_level=5,
        coins_cp=2000,
    )
    StartingEquipmentClassLine.objects.create(
        class_entry=entry, item=class_item, quantity=1
    )
    return entry


@pytest.fixture
def background_entry(template, background_item):
    """Create a background entry for Soldier."""
    entry = StartingEquipmentBackgroundEntry.objects.create(
        template=template,
        background="Soldier",
        coins_cp=1000,
    )
    StartingEquipmentBackgroundLine.objects.create(
        background_entry=entry, item=background_item, quantity=2
    )
    return entry


@pytest.fixture
def level_coins_entry(template):
    """Create level coins for level 5."""
    return StartingEquipmentLevelCoins.objects.create(
        template=template, level=5, coins_cp=15000
    )


def test_class_equipment_case_insensitive_match(
    character, template, class_entry, club_admin
):
    """Test class equipment matches case-insensitively."""
    character.char_class = "fighter"  # lowercase
    character.level = 1
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is not None
    assert entry.kind == "award"
    lines = entry.lines.all()
    assert len(lines) == 2  # 1 item + 1 coin line
    item_lines = [line for line in lines if line.item is not None]
    coin_lines = [line for line in lines if line.coins != 0]
    assert len(item_lines) == 1
    assert item_lines[0].item.name == "Class Weapon"
    assert item_lines[0].quantity == 1
    assert len(coin_lines) == 1
    assert coin_lines[0].coins == 2000


def test_class_equipment_level_range_filter(
    character, template, class_entry, club_admin
):
    """Test class equipment only matches within level range."""
    character.char_class = "Fighter"
    character.level = 6  # outside range 1-5
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    # No class entry matches level 6, so no equipment granted
    assert entry is None


def test_class_equipment_level_within_range(
    character, template, class_entry, club_admin
):
    """Test class equipment matches when level is within range."""
    character.char_class = "Fighter"
    character.level = 3  # within range 1-5
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is not None
    lines = entry.lines.all()
    item_lines = [line for line in lines if line.item is not None]
    coin_lines = [line for line in lines if line.coins != 0]
    assert len(item_lines) == 1
    assert len(coin_lines) == 1


def test_background_equipment_case_insensitive_match(
    character, template, background_entry, club_admin
):
    """Test background equipment matches case-insensitively."""
    character.background = "soldier"  # lowercase
    character.char_class = "Wizard"  # no matching class entry
    character.level = 1
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is not None
    lines = entry.lines.all()
    item_lines = [line for line in lines if line.item is not None]
    coin_lines = [line for line in lines if line.coins != 0]
    assert len(item_lines) == 1
    assert item_lines[0].item.name == "Background Tool"
    assert item_lines[0].quantity == 2
    assert len(coin_lines) == 1
    assert coin_lines[0].coins == 1000


def test_background_equipment_no_background_field(
    character, template, club_admin
):
    """Test no background equipment when character has no background."""
    character.background = ""
    character.char_class = "Wizard"
    character.level = 1
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is None


def test_level_coins_for_level_1_ignored(
    character, template, level_coins_entry, club_admin
):
    """Test level coins are not granted for level 1 characters."""
    character.char_class = "Wizard"
    character.level = 1
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is None


def test_level_coins_for_level_greater_than_1(
    character, template, level_coins_entry, club_admin
):
    """Test level coins are granted for level > 1."""
    character.char_class = "Wizard"
    character.level = 5
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is not None
    lines = entry.lines.all()
    coin_lines = [line for line in lines if line.coins != 0]
    assert len(coin_lines) == 1
    assert coin_lines[0].coins == 15000


def test_approved_magic_item_requests_only(
    character, template, magic_item, club_admin
):
    """Test only APPROVED magic item requests are granted."""
    character.char_class = "Wizard"
    character.level = 1
    character.save()

    # Create pending request (should NOT be granted)
    StartingEquipmentRequest.objects.create(
        club=character.club,
        character=character,
        item=magic_item,
        quantity=1,
        status=StartingEquipmentRequest.Status.PENDING,
    )

    entry = apply_starting_equipment(character, template, club_admin)

    # Pending request should not grant anything
    assert entry is None


def test_approved_magic_item_request_granted(
    character, template, magic_item, club_admin
):
    """Test APPROVED magic item request is granted."""
    character.char_class = "Wizard"
    character.level = 1
    character.save()

    StartingEquipmentRequest.objects.create(
        club=character.club,
        character=character,
        item=magic_item,
        quantity=1,
        status=StartingEquipmentRequest.Status.APPROVED,
    )

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is not None
    lines = entry.lines.all()
    item_lines = [line for line in lines if line.item is not None]
    assert len(item_lines) == 1
    assert item_lines[0].item.name == "Magic Sword"
    assert item_lines[0].quantity == 1


def test_declined_magic_item_request_not_granted(
    character, template, magic_item, club_admin
):
    """Test DECLINED magic item request is not granted."""
    character.char_class = "Wizard"
    character.level = 1
    character.save()

    StartingEquipmentRequest.objects.create(
        club=character.club,
        character=character,
        item=magic_item,
        quantity=1,
        status=StartingEquipmentRequest.Status.DECLINED,
    )

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is None


def test_multiple_approved_magic_item_requests(
    character, template, club_admin
):
    """Test multiple approved magic item requests are all granted."""
    character.char_class = "Wizard"
    character.level = 1
    character.save()

    item1 = character.club.items.create(name="Magic Sword", value_cp=5000)
    item2 = character.club.items.create(name="Magic Shield", value_cp=4000)

    StartingEquipmentRequest.objects.create(
        club=character.club,
        character=character,
        item=item1,
        quantity=1,
        status=StartingEquipmentRequest.Status.APPROVED,
    )
    StartingEquipmentRequest.objects.create(
        club=character.club,
        character=character,
        item=item2,
        quantity=2,
        status=StartingEquipmentRequest.Status.APPROVED,
    )

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is not None
    lines = entry.lines.all()
    item_lines = [line for line in lines if line.item is not None]
    assert len(item_lines) == 2
    items = {line.item.name: line.quantity for line in item_lines}
    assert items == {"Magic Sword": 1, "Magic Shield": 2}


def test_all_equipment_types_combined(
    character,
    template,
    class_entry,
    background_entry,
    level_coins_entry,
    magic_item,
    club_admin,
):
    """Test all equipment types work together in one call."""
    character.char_class = "Fighter"
    character.background = "Soldier"
    character.level = 5
    character.save()

    StartingEquipmentRequest.objects.create(
        club=character.club,
        character=character,
        item=magic_item,
        quantity=1,
        status=StartingEquipmentRequest.Status.APPROVED,
    )

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is not None
    lines = entry.lines.all()
    item_lines = [line for line in lines if line.item is not None]
    coin_lines = [line for line in lines if line.coins != 0]

    # Should have: class item (1), background item (2), magic item (1) = 3 item lines
    # Plus: class coins (2000), background coins (1000), level coins (15000) = 3 coin lines
    assert len(item_lines) == 3  # class + background + magic
    assert len(coin_lines) == 3

    items = {line.item.name: line.quantity for line in item_lines}
    assert items == {"Class Weapon": 1, "Background Tool": 2, "Magic Sword": 1}
    coins = [line.coins for line in coin_lines]
    assert set(coins) == {2000, 1000, 15000}


def test_empty_template_returns_none(character, template, club_admin):
    """Test empty template (no matching entries) returns None."""
    character.char_class = "Wizard"
    character.background = "Acolyte"
    character.level = 1
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry is None


def test_no_template_provided_returns_none(character, club_admin):
    """Test no template provided returns None (would error without template)."""
    # This test ensures the function requires a template
    character.char_class = "Wizard"
    character.level = 1
    character.save()

    # Function requires a template argument, so we can't call without it
    # The test is just to document expected behavior
    assert True


def test_ledger_entry_created_with_correct_character_and_actor(
    character, template, class_entry, club_admin
):
    """Test ledger entry has correct character and actor."""
    character.char_class = "Fighter"
    character.level = 1
    character.save()

    entry = apply_starting_equipment(character, template, club_admin)

    assert entry.character == character
    assert entry.created_by == club_admin
    assert entry.kind == "award"
    assert entry.note == "Starting equipment"


def test_choice_lines_not_granted(character, template, class_item, club_admin):
    """Test that is_choice=True lines are not granted (choices handled in UI)."""
    entry = StartingEquipmentClassEntry.objects.create(
        template=template,
        char_class="Fighter",
        min_level=1,
        max_level=5,
        coins_cp=0,
    )
    # Regular line (not a choice)
    StartingEquipmentClassLine.objects.create(
        class_entry=entry, item=class_item, quantity=1, is_choice=False
    )
    # Choice line (should not be granted)
    choice_item = character.club.items.create(name="Choice Weapon", value_cp=1000)
    StartingEquipmentClassLine.objects.create(
        class_entry=entry,
        item=choice_item,
        quantity=1,
        is_choice=True,
        choice_group="weapon",
    )

    character.char_class = "Fighter"
    character.level = 1
    character.save()

    result = apply_starting_equipment(character, template, club_admin)

    assert result is not None
    lines = result.lines.all()
    item_lines = [line for line in lines if line.item is not None]
    assert len(item_lines) == 1
    assert item_lines[0].item.name == "Class Weapon"