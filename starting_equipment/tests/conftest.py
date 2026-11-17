"""Fixtures for starting_equipment service tests."""

import pytest

from accounts.models import Membership, User
from items.models import Item
from player_characters.models import Character
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)


@pytest.fixture
def template(club):
    """Active starting equipment template for a club."""
    return StartingEquipmentTemplate.objects.create(
        club=club, name="Test Template", is_active=True, description="Test template"
    )


@pytest.fixture
def inactive_template(club):
    """Inactive starting equipment template."""
    return StartingEquipmentTemplate.objects.create(
        club=club, name="Inactive Template", is_active=False
    )


@pytest.fixture
def class_entry(template):
    """Class entry for Fighter at levels 1-20."""
    return StartingEquipmentClassEntry.objects.create(
        template=template, char_class="Fighter", min_level=1, max_level=20, coins_cp=1000
    )


@pytest.fixture
def class_entry_limited_level(template):
    """Class entry for Wizard at levels 5-10 only."""
    return StartingEquipmentClassEntry.objects.create(
        template=template, char_class="Wizard", min_level=5, max_level=10, coins_cp=500
    )


@pytest.fixture
def class_item(club):
    """Item for class equipment."""
    return Item.objects.create(club=club, name="Longsword", value_cp=1500)


@pytest.fixture
def class_item_2(club):
    """Second item for class equipment."""
    return Item.objects.create(club=club, name="Chain Mail", value_cp=7500)


@pytest.fixture
def class_line(class_entry, class_item):
    """Class line with an item (not a choice)."""
    return StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=class_item, quantity=1, is_choice=False
    )


@pytest.fixture
def class_line_choice(class_entry, class_item_2):
    """Class line that is a choice (should be skipped)."""
    return StartingEquipmentClassLine.objects.create(
        class_entry=class_entry,
        item=class_item_2,
        quantity=1,
        is_choice=True,
        choice_group="armor",
    )


@pytest.fixture
def bg_entry(template):
    """Background entry for Acolyte."""
    return StartingEquipmentBackgroundEntry.objects.create(
        template=template, background="Acolyte", coins_cp=500
    )


@pytest.fixture
def bg_item(club):
    """Item for background equipment."""
    return Item.objects.create(club=club, name="Holy Symbol", value_cp=500)


@pytest.fixture
def bg_line(bg_entry, bg_item):
    """Background line with an item (not a choice)."""
    return StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry, item=bg_item, quantity=1, is_choice=False
    )


@pytest.fixture
def bg_line_choice(bg_entry, bg_item):
    """Background line that is a choice (should be skipped)."""
    return StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry,
        item=bg_item,
        quantity=1,
        is_choice=True,
        choice_group="holy_item",
    )


@pytest.fixture
def level_coins(template):
    """Level coins for level 5."""
    return StartingEquipmentLevelCoins.objects.create(template=template, level=5, coins_cp=5000)


@pytest.fixture
def level_coins_lvl_10(template):
    """Level coins for level 10."""
    return StartingEquipmentLevelCoins.objects.create(template=template, level=10, coins_cp=15000)


@pytest.fixture
def magic_item(club):
    """Magic item for starting options."""
    return Item.objects.create(
        club=club,
        name="Potion of Healing",
        value_cp=5000,
        rarity="uncommon",
        magic_type="potion",
    )


@pytest.fixture
def magic_item_2(club):
    """Second magic item for starting options."""
    return Item.objects.create(
        club=club,
        name="Scroll of Fireball",
        value_cp=10000,
        rarity="rare",
        magic_type="scroll",
    )


@pytest.fixture
def magic_option(template, magic_item):
    """Magic item starting option."""
    return MagicItemStartingOption.objects.create(
        template=template, item=magic_item, max_per_character=1, notes="Level 1+ only"
    )


@pytest.fixture
def character_with_class_bg(club, player, class_entry, bg_entry):
    """Character with class and background matching template entries."""
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="Test Fighter",
        char_class="Fighter",
        background="Acolyte",
        level=1,
    )


@pytest.fixture
def character_lowercase_class_bg(club, player, class_entry, bg_entry):
    """Character with lowercase class and background (case-insensitive match)."""
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="Test Fighter Lower",
        char_class="fighter",
        background="acolyte",
        level=1,
    )


@pytest.fixture
def character_level_5(club, player, class_entry, bg_entry):
    """Character at level 5."""
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="Test Fighter L5",
        char_class="Fighter",
        background="Acolyte",
        level=5,
    )


@pytest.fixture
def character_level_10(club, player, class_entry, bg_entry):
    """Character at level 10."""
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="Test Fighter L10",
        char_class="Fighter",
        background="Acolyte",
        level=10,
    )


@pytest.fixture
def character_level_3_wizard(club, player, class_entry_limited_level):
    """Wizard character at level 3 (outside class entry range)."""
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="Young Wizard",
        char_class="Wizard",
        background="Sage",
        level=3,
    )


@pytest.fixture
def character_level_7_wizard(club, player, class_entry_limited_level):
    """Wizard character at level 7 (inside class entry range)."""
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="Mid Wizard",
        char_class="Wizard",
        background="Sage",
        level=7,
    )


@pytest.fixture
def character_no_bg(club, player, class_entry):
    """Character with class but no background."""
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="No Background",
        char_class="Fighter",
        background="",
        level=1,
    )


@pytest.fixture
def character_no_class(club, player, bg_entry):
    """Character with background but no class."""
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="No Class",
        char_class="",
        background="Acolyte",
        level=1,
    )


@pytest.fixture
def approved_request(character_with_class_bg, magic_option):
    """Approved magic item request."""
    return StartingEquipmentRequest.objects.create(
        club=character_with_class_bg.club,
        character=character_with_class_bg,
        item=magic_option.item,
        quantity=1,
        status=StartingEquipmentRequest.Status.APPROVED,
    )


@pytest.fixture
def pending_request(character_with_class_bg, magic_item_2):
    """Pending magic item request."""
    return StartingEquipmentRequest.objects.create(
        club=character_with_class_bg.club,
        character=character_with_class_bg,
        item=magic_item_2,
        quantity=1,
        status=StartingEquipmentRequest.Status.PENDING,
    )


@pytest.fixture
def declined_request(character_with_class_bg, magic_item_2):
    """Declined magic item request."""
    return StartingEquipmentRequest.objects.create(
        club=character_with_class_bg.club,
        character=character_with_class_bg,
        item=magic_item_2,
        quantity=1,
        status=StartingEquipmentRequest.Status.DECLINED,
    )


@pytest.fixture
def game_master_user(club):
    """Game master user for actor parameter."""
    return User.objects.create_user(
        "gm_test@example.com", password="pw", display_name="Test GM"
    )


@pytest.fixture
def empty_template(club):
    """Template with no class/background/level entries."""
    return StartingEquipmentTemplate.objects.create(
        club=club, name="Empty Template", is_active=True
    )