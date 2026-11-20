"""Service for seeding default starting equipment templates.

This module contains the data constants and the seeding logic extracted from
the `seed_starting_equipment` management command, so it can be called
programmatically (e.g., during club creation).
"""

from dataclasses import dataclass

from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction

from accounts.models import Club
from character_options.models import Background, CharacterClass
from character_options.services import seed_default_options
from items.models import Item
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentTemplate,
)

# 2024 D&D Class starting equipment (PHB 2024)
CLASS_EQUIPMENT = {
    "Barbarian": {
        "coins_cp": 200,  # 2d4 × 10 gp average = 50 gp = 5000 cp, but 2024 uses fixed
        "items": [
            ("Greataxe", 3000, "🪓", "standard", "", 1, False, ""),
            ("Handaxe", 500, "🪓", "standard", "", 2, False, ""),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, False, ""),
            ("Javelin", 50, "🏹", "standard", "", 4, False, ""),
        ],
        "choices": [
            # Greataxe OR any martial melee weapon - we'll use Greataxe as default
            # Two handaxes OR any simple weapon - we'll use Handaxe as default
        ],
    },
    "Bard": {
        "coins_cp": 1000,  # 5d4 × 10 gp average = 125 gp
        "items": [
            ("Rapier", 2500, "🗡️", "fine", "", 1, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 1, False, ""),
            ("Diplomat's Pack", 3900, "🎒", "standard", "", 1, False, ""),
            ("Lute", 3500, "🎵", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Rapier OR longsword OR any simple weapon
            # Diplomat's pack OR entertainer's pack
            # Lute OR any musical instrument
        ],
    },
    "Cleric": {
        "coins_cp": 500,  # 5d4 × 10 gp
        "items": [
            ("Mace", 500, "⚔️", "standard", "", 1, False, ""),
            ("Scale Mail", 5000, "🛡️", "standard", "", 1, False, ""),
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, False, ""),
            ("Crossbow Bolt", 1, "🏹", "trivial", "", 20, False, ""),
            ("Priest's Pack", 1900, "🎒", "standard", "", 1, False, ""),
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Holy Symbol (Amulet)", 500, "✝️", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Mace OR warhammer
            # Scale mail OR leather armor OR chain mail
            # Light crossbow + 20 bolts OR any simple weapon
            # Priest's pack OR explorer's pack
        ],
    },
    "Druid": {
        "coins_cp": 200,  # 2d4 × 10 gp
        "items": [
            ("Wooden Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Scimitar", 2500, "🗡️", "fine", "", 1, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, False, ""),
            ("Druidic Focus (Staff)", 500, "🪄", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Wooden shield OR any simple weapon
            # Scimitar OR any simple melee weapon
        ],
    },
    "Fighter": {
        "coins_cp": 500,  # 5d4 × 10 gp
        "items": [
            ("Chain Mail", 7500, "🛡️", "standard", "", 1, False, ""),
            ("Longsword", 1500, "🗡️", "fine", "", 1, False, ""),
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, False, ""),
            ("Crossbow Bolt", 1, "🏹", "trivial", "", 20, False, ""),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Chain mail OR leather armor + longbow + 20 arrows
            # Martial weapon + shield OR two martial weapons
            # Light crossbow + 20 bolts OR two handaxes
            # Dungeoneer's pack OR explorer's pack
        ],
    },
    "Monk": {
        "coins_cp": 50,  # 5d4 gp (not ×10)
        "items": [
            ("Shortsword", 1000, "🗡️", "fine", "", 1, False, ""),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, False, ""),
            ("Dart", 5, "🏹", "trivial", "", 10, False, ""),
        ],
        "choices": [
            # Shortsword OR any simple weapon
            # Dungeoneer's pack OR explorer's pack
        ],
    },
    "Paladin": {
        "coins_cp": 1500,  # 5d4 × 10 gp
        "items": [
            ("Longsword", 1500, "🗡️", "fine", "", 1, False, ""),
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Javelin", 50, "🏹", "standard", "", 5, False, ""),
            ("Priest's Pack", 1900, "🎒", "standard", "", 1, False, ""),
            ("Chain Mail", 7500, "🛡️", "standard", "", 1, False, ""),
            ("Holy Symbol (Amulet)", 500, "✝️", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Martial weapon + shield OR two martial weapons
            # Five javelins OR any simple melee weapon
            # Priest's pack OR explorer's pack
        ],
    },
    "Ranger": {
        "coins_cp": 1000,  # 5d4 × 10 gp
        "items": [
            ("Scale Mail", 5000, "🛡️", "standard", "", 1, False, ""),
            ("Shortsword", 1000, "🗡️", "fine", "", 2, False, ""),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, False, ""),
            ("Longbow", 5000, "🏹", "fine", "", 1, False, ""),
            ("Arrow", 1, "🏹", "trivial", "", 20, False, ""),
        ],
        "choices": [
            # Scale mail OR leather armor
            # Two shortswords OR two simple melee weapons
            # Dungeoneer's pack OR explorer's pack
        ],
    },
    "Rogue": {
        "coins_cp": 400,  # 4d4 × 10 gp
        "items": [
            ("Rapier", 2500, "🗡️", "fine", "", 1, False, ""),
            ("Shortbow", 2500, "🏹", "fine", "", 1, False, ""),
            ("Arrow", 1, "🏹", "trivial", "", 20, False, ""),
            ("Burglar's Pack", 1600, "🎒", "standard", "", 1, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
            ("Thieves' Tools", 2500, "🔧", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Rapier OR shortsword
            # Shortbow + 20 arrows OR shortsword
            # Burglar's pack OR dungeoneer's pack OR explorer's pack
        ],
    },
    "Sorcerer": {
        "coins_cp": 300,  # 3d4 × 10 gp
        "items": [
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, False, ""),
            ("Crossbow Bolt", 1, "🏹", "trivial", "", 20, False, ""),
            ("Component Pouch", 2500, "💼", "standard", "", 1, False, ""),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
        ],
        "choices": [
            # Light crossbow + 20 bolts OR any simple weapon
            # Component pouch OR arcane focus
            # Dungeoneer's pack OR explorer's pack
        ],
    },
    "Warlock": {
        "coins_cp": 1000,  # 4d4 × 10 gp
        "items": [
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, False, ""),
            ("Crossbow Bolt", 1, "🏹", "trivial", "", 20, False, ""),
            ("Component Pouch", 2500, "💼", "standard", "", 1, False, ""),
            ("Scholar's Pack", 4000, "🎒", "standard", "", 1, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
        ],
        "choices": [
            # Light crossbow + 20 bolts OR any simple weapon
            # Component pouch OR arcane focus
            # Scholar's pack OR dungeoneer's pack
        ],
    },
    "Wizard": {
        "coins_cp": 200,  # 4d4 × 10 gp
        "items": [
            ("Quarterstaff", 200, "🪄", "standard", "", 1, False, ""),
            ("Component Pouch", 2500, "💼", "standard", "", 1, False, ""),
            ("Scholar's Pack", 4000, "🎒", "standard", "", 1, False, ""),
            ("Spellbook", 5000, "📖", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Quarterstaff OR dagger
            # Component pouch OR arcane focus
            # Scholar's pack OR explorer's pack
        ],
    },
}

# 2024 D&D Background starting equipment (PHB 2024)
BACKGROUND_EQUIPMENT = {
    "Acolyte": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Holy Symbol (Amulet)", 500, "✝️", "standard", "", 1, False, ""),
            ("Prayer Book", 500, "📖", "standard", "", 1, False, ""),
            ("Incense (5 sticks)", 10, "🕯️", "trivial", "", 5, False, ""),
            ("Vestments", 500, "👘", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Artisan": {
        "coins_cp": 2000,  # 20 gp
        "items": [
            ("Artisan's Tools", 2000, "🔨", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Charlatan": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
            ("Disguise Kit", 2500, "🎭", "standard", "", 1, False, ""),
            ("Forgery Kit", 1500, "📝", "standard", "", 1, False, ""),
        ],
    },
    "Criminal": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Crowbar", 200, "🔨", "standard", "", 1, False, ""),
            ("Dark Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Entertainer": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Musical Instrument (Lute)", 3500, "🎵", "standard", "", 1, False, ""),
            ("Costume", 500, "🎭", "standard", "", 1, False, ""),
            ("Mirror", 500, "🪞", "standard", "", 1, False, ""),
        ],
    },
    "Farmer": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Carpenter's Tools", 1000, "🔨", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Guard": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Uniform", 500, "👕", "standard", "", 1, False, ""),
            ("Horn", 300, "📯", "standard", "", 1, False, ""),
            ("Manacles", 200, "⛓️", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Guide": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Navigator's Tools", 2500, "🧭", "standard", "", 1, False, ""),
            ("Walking Stick", 10, "🦯", "trivial", "", 1, False, ""),
            ("Traveler's Clothes", 200, "👕", "standard", "", 1, False, ""),
        ],
    },
    "Hermit": {
        "coins_cp": 500,  # 5 gp
        "items": [
            ("Herbalism Kit", 500, "🌿", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Merchant": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Merchant's Scale", 500, "⚖️", "standard", "", 1, False, ""),
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
        ],
    },
    "Noble": {
        "coins_cp": 2500,  # 25 gp
        "items": [
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
            ("Signet Ring", 500, "💍", "standard", "", 1, False, ""),
            ("Scroll of Pedigree", 100, "📜", "trivial", "", 1, False, ""),
        ],
    },
    "Sage": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Ink Pen", 20, "🖋️", "trivial", "", 1, False, ""),
            ("Ink (1 oz)", 100, "🖋️", "trivial", "", 1, False, ""),
            ("Parchment (10 sheets)", 100, "📜", "trivial", "", 10, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Sailor": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Navigator's Tools", 2500, "🧭", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Scribe": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Calligrapher's Supplies", 1000, "🖋️", "standard", "", 1, False, ""),
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
        ],
    },
    "Soldier": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Insignia of Rank", 100, "🎖️", "trivial", "", 1, False, ""),
            ("Gaming Set (Dice)", 100, "🎲", "trivial", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Wayfarer": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Thieves' Tools", 2500, "🔧", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
}

# DMG 2024 Starting Equipment at Higher Levels - additional coins per level tier
# These are ADDITIONAL coins on top of class + background equipment
LEVEL_COINS_CP = {
    # Level: additional coins in cp
    2: 25000,  # 250 gp
    3: 25000,
    4: 25000,
    5: 50000,  # 500 gp
    6: 50000,
    7: 50000,
    8: 50000,
    9: 50000,
    10: 50000,
    11: 75000,  # 750 gp
    12: 75000,
    13: 75000,
    14: 75000,
    15: 75000,
    16: 75000,
    17: 100000,  # 1000 gp
    18: 100000,
    19: 100000,
    20: 100000,
}

DEFAULT_TEMPLATE_NAME = "2024 D&D Default"
DEFAULT_TEMPLATE_DESCRIPTION = (
    "Default starting equipment per 2024 D&D Player's Handbook and Dungeon Master's Guide."
)


class StartingEquipmentSeedError(Exception):
    """Raised when seeding starting equipment fails."""


@dataclass
class SeedSummary:
    """Summary of a seeding operation."""

    template_created: bool = False
    skipped: bool = False
    items_created: int = 0
    class_entries_created: int = 0
    class_entries_updated: int = 0
    background_entries_created: int = 0
    background_entries_updated: int = 0
    level_coins_created: int = 0
    level_coins_updated: int = 0


def _create_items(club: Club) -> int:
    """Create all items needed for class and background equipment.

    Returns the number of items created.
    """
    item_specs = {}

    # Collect all unique items from class equipment
    for class_data in CLASS_EQUIPMENT.values():
        for item_data in class_data["items"]:
            name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
            if name not in item_specs:
                item_specs[name] = {
                    "value_cp": value_cp,
                    "symbol": symbol,
                    "rarity": rarity,
                    "magic_type": magic_type,
                }

    # Collect all unique items from background equipment
    for bg_data in BACKGROUND_EQUIPMENT.values():
        for item_data in bg_data["items"]:
            name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
            if name not in item_specs:
                item_specs[name] = {
                    "value_cp": value_cp,
                    "symbol": symbol,
                    "rarity": rarity,
                    "magic_type": magic_type,
                }

    # Create items
    created_count = 0
    for name, specs in item_specs.items():
        try:
            item, created = Item.objects.get_or_create(
                club=club,
                name=name,
                defaults=specs,
            )
        except MultipleObjectsReturned as err:
            raise StartingEquipmentSeedError(
                f"Multiple items named '{name}' exist for club {club}. "
                "Please resolve duplicates in the admin before seeding."
            ) from err
        if created:
            created_count += 1

    return created_count


def _get_item(club: Club, name: str) -> Item:
    """Get item by name, raise if not found."""
    try:
        return Item.objects.for_club(club).get(name=name)
    except Item.DoesNotExist as err:
        raise StartingEquipmentSeedError(
            f"Item '{name}' not found for club {club}. Run without --force first to create items."
        ) from err
    except MultipleObjectsReturned as err:
        raise StartingEquipmentSeedError(
            f"Multiple items named '{name}' exist for club {club}. "
            "Please resolve duplicates in the admin before seeding."
        ) from err


def _create_class_entries(template: StartingEquipmentTemplate, force: bool) -> tuple[int, int]:
    """Create StartingEquipmentClassEntry for each class.

    Returns (created_count, updated_count).
    """
    club = template.club
    created_count = 0
    updated_count = 0

    for class_name, class_data in CLASS_EQUIPMENT.items():
        class_option = CharacterClass.objects.for_club(club).get(name=class_name)
        entry, created = StartingEquipmentClassEntry.objects.get_or_create(
            template=template,
            class_option=class_option,
            defaults={
                "min_level": 1,
                "max_level": 20,
                "coins_cp": class_data["coins_cp"],
            },
        )
        if created:
            created_count += 1
        elif force:
            entry.coins_cp = class_data["coins_cp"]
            entry.save(update_fields=["coins_cp"])
            updated_count += 1

        # Create lines for this class entry
        for item_data in class_data["items"]:
            name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
            item = _get_item(club, name)
            line, line_created = StartingEquipmentClassLine.objects.get_or_create(
                class_entry=entry,
                item=item,
                defaults={
                    "quantity": qty,
                    "is_choice": is_choice,
                    "choice_group": choice_group,
                },
            )
            if line_created:
                pass  # count not tracked for lines
            elif force:
                line.quantity = qty
                line.is_choice = is_choice
                line.choice_group = choice_group
                line.save(update_fields=["quantity", "is_choice", "choice_group"])

    return created_count, updated_count


def _create_background_entries(template: StartingEquipmentTemplate, force: bool) -> tuple[int, int]:
    """Create StartingEquipmentBackgroundEntry for each background.

    Returns (created_count, updated_count).
    """
    club = template.club
    created_count = 0
    updated_count = 0

    for bg_name, bg_data in BACKGROUND_EQUIPMENT.items():
        bg_option = Background.objects.for_club(club).get(name=bg_name)
        entry, created = StartingEquipmentBackgroundEntry.objects.get_or_create(
            template=template,
            background_option=bg_option,
            defaults={
                "coins_cp": bg_data["coins_cp"],
            },
        )
        if created:
            created_count += 1
        elif force:
            entry.coins_cp = bg_data["coins_cp"]
            entry.save(update_fields=["coins_cp"])
            updated_count += 1

        # Create lines for this background entry
        for item_data in bg_data["items"]:
            name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
            item = _get_item(club, name)
            line, line_created = StartingEquipmentBackgroundLine.objects.get_or_create(
                background_entry=entry,
                item=item,
                defaults={
                    "quantity": qty,
                    "is_choice": is_choice,
                    "choice_group": choice_group,
                },
            )
            if line_created:
                pass
            elif force:
                line.quantity = qty
                line.is_choice = is_choice
                line.choice_group = choice_group
                line.save(update_fields=["quantity", "is_choice", "choice_group"])

    return created_count, updated_count


def _create_level_coins(template: StartingEquipmentTemplate, force: bool) -> tuple[int, int]:
    """Create StartingEquipmentLevelCoins for levels 2-20.

    Returns (created_count, updated_count).
    """
    created_count = 0
    updated_count = 0

    for level, coins_cp in LEVEL_COINS_CP.items():
        lc, created = StartingEquipmentLevelCoins.objects.get_or_create(
            template=template,
            level=level,
            defaults={"coins_cp": coins_cp},
        )
        if created:
            created_count += 1
        elif force:
            lc.coins_cp = coins_cp
            lc.save(update_fields=["coins_cp"])
            updated_count += 1

    return created_count, updated_count


def seed_default_starting_equipment(
    club: Club,
    *,
    name: str = DEFAULT_TEMPLATE_NAME,
    force: bool = False,
) -> SeedSummary:
    """Seed the default starting equipment template for a club.

    This function is idempotent: if the template already exists and `force`
    is False, it returns a summary with `skipped=True` and makes no changes.
    If `force` is True, existing entries are updated to match the default data.

    Args:
        club: The club to seed equipment for.
        name: Name of the template (default: "2024 D&D Default").
        force: If True, update existing entries; if False, skip when template exists.

    Returns:
        SeedSummary with counts of created/updated objects.

    Raises:
        StartingEquipmentSeedError: If duplicate items exist or items are missing.
    """
    with transaction.atomic():
        # First, seed default character options (classes, backgrounds) for this club
        seed_default_options(club)

        # Create or get template
        template, created = StartingEquipmentTemplate.objects.get_or_create(
            club=club,
            name=name,
            defaults={
                "description": DEFAULT_TEMPLATE_DESCRIPTION,
                "is_active": True,
            },
        )

        summary = SeedSummary(template_created=created)

        if not created and not force:
            summary.skipped = True
            return summary

        # Create all items needed
        summary.items_created = _create_items(club)

        # Create class entries
        (
            summary.class_entries_created,
            summary.class_entries_updated,
        ) = _create_class_entries(template, force)

        # Create background entries
        (
            summary.background_entries_created,
            summary.background_entries_updated,
        ) = _create_background_entries(template, force)

        # Create level coins
        (
            summary.level_coins_created,
            summary.level_coins_updated,
        ) = _create_level_coins(template, force)

        return summary
