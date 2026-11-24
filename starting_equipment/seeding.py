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
from items.pack_seeding import PackSeedingError, seed_pack_containers
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentTemplate,
)

# SRD weights (lb) for starting-equipment items that have a listed weight.
# Values match shops/gear.py for overlapping names; weight is per unit for
# stacked items (Arrows, Crossbow Bolts). Items not listed here have no
# listed SRD weight and are left blank.
STARTING_EQUIPMENT_WEIGHTS: dict[str, float] = {
    "Leather Armor": 5,
    "Component Pouch": 2,
    "Amulet (Holy Symbol)": 1,
    "Crowbar": 5,
    "Costume": 4,
    "Arrows": 0.05,
    "Crossbow Bolts": 0.1,
    "Longsword": 4,
    "Greataxe": 7,
    "Shield": 6,
    "Chain Mail": 55,
    "Scale Mail": 45,
    "Spellbook": 3,
    "Thieves' Tools": 1,
    "Dart": 0.25,
}

# Stacked ammunition items shared with the General Store gear list.
# Each entry: name -> (value_cp, symbol, rarity, magic_type, unit_name, value_units)
# These match shops/gear.py GENERAL_STORE_GEAR exactly.
STACKED_AMMO_SPECS = {
    "Arrows": (100, "🏹", "trivial", "", "arrow", 20),
    "Crossbow Bolts": (100, "🏹", "trivial", "", "bolt", 20),
    "Firearm Bullets": (300, "⚪", "trivial", "", "bullet", 10),
    "Sling Bullets": (4, "⚪", "trivial", "", "bullet", 20),
    "Needles": (100, "📌", "trivial", "", "needle", 50),
}

# 2024 D&D Class starting equipment (PHB 2024)
# Each item tuple: (name, value_cp, symbol, rarity, magic_type, quantity, is_choice, choice_group)
#
# Modelling rules for choice groups:
# - Each "X or Y" in the PHB is one choice group. Every option in it is an
#   is_choice=True line with the same choice_group slug (<=50 chars, unique per entry).
# - The DEFAULT option (the "X") is the FIRST line of its group. A claim grants every
#   fixed line plus the first line of each group. The default is never also a fixed line.
# - One option = one line (item + quantity). Compound options are simplified:
#   "light crossbow + 20 bolts" keeps the crossbow in the group and the ammo stays a
#   fixed line; "leather armor + longbow + 20 arrows" (Fighter) is just Leather Armor.
# - "any martial/simple weapon" is a short curated list of named catalogue items.
# - Pack choices list the real packs by name; Entertainer's Pack enters the catalogue here.
# - An item may sit in two groups of one entry (Rogue Shortsword), but never in a group
#   and as a fixed line of the same entry.
#
# Ammunition items use stacked catalogue items (Arrows, Crossbow Bolts) with quantity
# in UNITS (e.g., 20 arrows), not as separate plain items. The value_cp and symbol
# match the gear list; the item's value_units defines the bundle size.
CLASS_EQUIPMENT = {
    "Barbarian": {
        "coins_cp": 200,  # 2d4 × 10 gp average = 50 gp = 5000 cp, but 2024 uses fixed
        "items": [
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, False, ""),
            ("Javelin", 50, "🏹", "standard", "", 4, False, ""),
            # weapon: Greataxe OR any martial melee weapon
            ("Greataxe", 3000, "🪓", "standard", "", 1, True, "weapon"),
            ("Battleaxe", 1000, "🪓", "standard", "", 1, True, "weapon"),
            ("Longsword", 1500, "🗡️", "fine", "", 1, True, "weapon"),
            ("Warhammer", 1500, "⚔️", "standard", "", 1, True, "weapon"),
            # simple_weapon: Two handaxes OR any simple weapon
            ("Handaxe", 500, "🪓", "standard", "", 2, True, "simple_weapon"),
            ("Mace", 500, "⚔️", "standard", "", 1, True, "simple_weapon"),
            ("Spear", 100, "🏹", "standard", "", 1, True, "simple_weapon"),
            ("Quarterstaff", 200, "🪄", "standard", "", 1, True, "simple_weapon"),
        ],
    },
    "Bard": {
        "coins_cp": 1000,  # 5d4 × 10 gp average = 125 gp
        "items": [
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 1, False, ""),
            # weapon: Rapier OR longsword OR any simple weapon
            ("Rapier", 2500, "🗡️", "fine", "", 1, True, "weapon"),
            ("Longsword", 1500, "🗡️", "fine", "", 1, True, "weapon"),
            ("Mace", 500, "⚔️", "standard", "", 1, True, "weapon"),
            ("Spear", 100, "🏹", "standard", "", 1, True, "weapon"),
            # pack: Diplomat's pack OR entertainer's pack
            ("Diplomat's Pack", 3900, "🎒", "standard", "", 1, True, "pack"),
            ("Entertainer's Pack", 4000, "🎒", "standard", "", 1, True, "pack"),
            # instrument: Lute OR any musical instrument
            ("Lute (Musical Instrument)", 3500, "🎵", "standard", "", 1, True, "instrument"),
            ("Flute (Musical Instrument)", 200, "🎵", "standard", "", 1, True, "instrument"),
            ("Lyre (Musical Instrument)", 300, "🎵", "standard", "", 1, True, "instrument"),
            ("Horn (Musical Instrument)", 300, "📯", "standard", "", 1, True, "instrument"),
        ],
    },
    "Cleric": {
        "coins_cp": 500,  # 5d4 × 10 gp
        "items": [
            ("Crossbow Bolts", 100, "🏹", "trivial", "", 20, False, ""),
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Amulet (Holy Symbol)", 500, "✝️", "standard", "", 1, False, ""),
            # melee_weapon: Mace OR warhammer
            ("Mace", 500, "⚔️", "standard", "", 1, True, "melee_weapon"),
            ("Warhammer", 1500, "⚔️", "standard", "", 1, True, "melee_weapon"),
            # armor: Scale mail OR leather armor OR chain mail
            ("Scale Mail", 5000, "🛡️", "standard", "", 1, True, "armor"),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, True, "armor"),
            ("Chain Mail", 7500, "🛡️", "standard", "", 1, True, "armor"),
            # ranged: Light crossbow + 20 bolts OR any simple weapon (bolts stay fixed)
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, True, "ranged"),
            ("Shortbow", 2500, "🏹", "fine", "", 1, True, "ranged"),
            ("Handaxe", 500, "🪓", "standard", "", 1, True, "ranged"),
            ("Javelin", 50, "🏹", "standard", "", 1, True, "ranged"),
            # pack: Priest's pack OR explorer's pack
            ("Priest's Pack", 3300, "🎒", "standard", "", 1, True, "pack"),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
    "Druid": {
        "coins_cp": 200,  # 2d4 × 10 gp
        "items": [
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, False, ""),
            ("Staff (Druidic Focus)", 500, "🪄", "standard", "", 1, False, ""),
            # shield_or_weapon: Wooden shield OR any simple weapon
            ("Wooden Shield", 1000, "🛡️", "standard", "", 1, True, "shield_or_weapon"),
            ("Quarterstaff", 200, "🪄", "standard", "", 1, True, "shield_or_weapon"),
            ("Spear", 100, "🏹", "standard", "", 1, True, "shield_or_weapon"),
            ("Club", 10, "⚔️", "standard", "", 1, True, "shield_or_weapon"),
            # melee: Scimitar OR any simple melee weapon
            ("Scimitar", 2500, "🗡️", "fine", "", 1, True, "melee"),
            ("Sickle", 100, "🔪", "standard", "", 1, True, "melee"),
            ("Dagger", 200, "🗡️", "standard", "", 1, True, "melee"),
            ("Handaxe", 500, "🪓", "standard", "", 1, True, "melee"),
        ],
    },
    "Fighter": {
        "coins_cp": 500,  # 5d4 × 10 gp
        "items": [
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Crossbow Bolts", 100, "🏹", "trivial", "", 20, False, ""),
            # armor: Chain mail OR leather armor + longbow + 20 arrows.
            # Simplified to one line per option: the alternative is Leather Armor only.
            ("Chain Mail", 7500, "🛡️", "standard", "", 1, True, "armor"),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, True, "armor"),
            # weapons: Martial weapon + shield OR two martial weapons (shield stays fixed)
            ("Longsword", 1500, "🗡️", "fine", "", 1, True, "weapons"),
            ("Battleaxe", 1000, "🪓", "standard", "", 1, True, "weapons"),
            ("Warhammer", 1500, "⚔️", "standard", "", 1, True, "weapons"),
            ("Greatsword", 5000, "🗡️", "fine", "", 1, True, "weapons"),
            # ranged: Light crossbow + 20 bolts OR two handaxes (bolts stay fixed)
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, True, "ranged"),
            ("Handaxe", 500, "🪓", "standard", "", 2, True, "ranged"),
            # pack: Dungeoneer's pack OR explorer's pack
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, True, "pack"),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
    "Monk": {
        "coins_cp": 50,  # 5d4 gp (not ×10)
        "items": [
            ("Dart", 5, "🏹", "trivial", "", 10, False, ""),
            # weapon: Shortsword OR any simple weapon
            ("Shortsword", 1000, "🗡️", "fine", "", 1, True, "weapon"),
            ("Spear", 100, "🏹", "standard", "", 1, True, "weapon"),
            ("Quarterstaff", 200, "🪄", "standard", "", 1, True, "weapon"),
            ("Handaxe", 500, "🪓", "standard", "", 1, True, "weapon"),
            # pack: Dungeoneer's pack OR explorer's pack
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, True, "pack"),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
    "Paladin": {
        "coins_cp": 1500,  # 5d4 × 10 gp
        "items": [
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Chain Mail", 7500, "🛡️", "standard", "", 1, False, ""),
            ("Amulet (Holy Symbol)", 500, "✝️", "standard", "", 1, False, ""),
            # weapons: Martial weapon + shield OR two martial weapons (shield stays fixed)
            ("Longsword", 1500, "🗡️", "fine", "", 1, True, "weapons"),
            ("Battleaxe", 1000, "🪓", "standard", "", 1, True, "weapons"),
            ("Warhammer", 1500, "⚔️", "standard", "", 1, True, "weapons"),
            ("Greatsword", 5000, "🗡️", "fine", "", 1, True, "weapons"),
            # ranged: Five javelins OR any simple melee weapon
            ("Javelin", 50, "🏹", "standard", "", 5, True, "ranged"),
            ("Spear", 100, "🏹", "standard", "", 1, True, "ranged"),
            ("Mace", 500, "⚔️", "standard", "", 1, True, "ranged"),
            ("Handaxe", 500, "🪓", "standard", "", 1, True, "ranged"),
            # pack: Priest's pack OR explorer's pack
            ("Priest's Pack", 3300, "🎒", "standard", "", 1, True, "pack"),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
    "Ranger": {
        "coins_cp": 1000,  # 5d4 × 10 gp
        "items": [
            ("Longbow", 5000, "🏹", "fine", "", 1, False, ""),
            ("Arrows", 100, "🏹", "trivial", "", 20, False, ""),
            # armor: Scale mail OR leather armor
            ("Scale Mail", 5000, "🛡️", "standard", "", 1, True, "armor"),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, True, "armor"),
            # weapons: Two shortswords OR two simple melee weapons
            ("Shortsword", 1000, "🗡️", "fine", "", 2, True, "weapons"),
            ("Handaxe", 500, "🪓", "standard", "", 2, True, "weapons"),
            ("Spear", 100, "🏹", "standard", "", 2, True, "weapons"),
            # pack: Dungeoneer's pack OR explorer's pack
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, True, "pack"),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
    "Rogue": {
        "coins_cp": 400,  # 4d4 × 10 gp
        "items": [
            ("Arrows", 100, "🏹", "trivial", "", 20, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
            ("Thieves' Tools", 2500, "🔧", "standard", "", 1, False, ""),
            # weapon: Rapier OR shortsword
            ("Rapier", 2500, "🗡️", "fine", "", 1, True, "weapon"),
            ("Shortsword", 1000, "🗡️", "fine", "", 1, True, "weapon"),
            # ranged: Shortbow + 20 arrows OR shortsword (arrows stay fixed)
            ("Shortbow", 2500, "🏹", "fine", "", 1, True, "ranged"),
            ("Shortsword", 1000, "🗡️", "fine", "", 1, True, "ranged"),
            # pack: Burglar's pack OR dungeoneer's pack OR explorer's pack
            ("Burglar's Pack", 1600, "🎒", "standard", "", 1, True, "pack"),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, True, "pack"),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
    "Sorcerer": {
        "coins_cp": 300,  # 3d4 × 10 gp
        "items": [
            ("Crossbow Bolts", 100, "🏹", "trivial", "", 20, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
            # ranged: Light crossbow + 20 bolts OR any simple weapon (bolts stay fixed)
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, True, "ranged"),
            ("Quarterstaff", 200, "🪄", "standard", "", 1, True, "ranged"),
            ("Spear", 100, "🏹", "standard", "", 1, True, "ranged"),
            ("Handaxe", 500, "🪓", "standard", "", 1, True, "ranged"),
            # focus: Component pouch OR arcane focus
            ("Component Pouch", 2500, "💼", "standard", "", 1, True, "focus"),
            ("Crystal (Arcane Focus)", 1000, "💎", "standard", "", 1, True, "focus"),
            ("Orb (Arcane Focus)", 2000, "🔮", "standard", "", 1, True, "focus"),
            ("Rod (Arcane Focus)", 1000, "🪄", "standard", "", 1, True, "focus"),
            ("Staff (Arcane Focus)", 500, "🪄", "standard", "", 1, True, "focus"),
            ("Wand (Arcane Focus)", 1000, "🪄", "standard", "", 1, True, "focus"),
            # pack: Dungeoneer's pack OR explorer's pack
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, True, "pack"),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
    "Warlock": {
        "coins_cp": 1000,  # 4d4 × 10 gp
        "items": [
            ("Crossbow Bolts", 100, "🏹", "trivial", "", 20, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
            # ranged: Light crossbow + 20 bolts OR any simple weapon (bolts stay fixed)
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, True, "ranged"),
            ("Quarterstaff", 200, "🪄", "standard", "", 1, True, "ranged"),
            ("Spear", 100, "🏹", "standard", "", 1, True, "ranged"),
            ("Handaxe", 500, "🪓", "standard", "", 1, True, "ranged"),
            # focus: Component pouch OR arcane focus
            ("Component Pouch", 2500, "💼", "standard", "", 1, True, "focus"),
            ("Crystal (Arcane Focus)", 1000, "💎", "standard", "", 1, True, "focus"),
            ("Orb (Arcane Focus)", 2000, "🔮", "standard", "", 1, True, "focus"),
            ("Rod (Arcane Focus)", 1000, "🪄", "standard", "", 1, True, "focus"),
            ("Staff (Arcane Focus)", 500, "🪄", "standard", "", 1, True, "focus"),
            ("Wand (Arcane Focus)", 1000, "🪄", "standard", "", 1, True, "focus"),
            # pack: Scholar's pack OR dungeoneer's pack
            ("Scholar's Pack", 4000, "🎒", "standard", "", 1, True, "pack"),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
    "Wizard": {
        "coins_cp": 200,  # 4d4 × 10 gp
        "items": [
            ("Spellbook", 5000, "📖", "standard", "", 1, False, ""),
            # weapon: Quarterstaff OR dagger
            ("Quarterstaff", 200, "🪄", "standard", "", 1, True, "weapon"),
            ("Dagger", 200, "🗡️", "standard", "", 1, True, "weapon"),
            # focus: Component pouch OR arcane focus
            ("Component Pouch", 2500, "💼", "standard", "", 1, True, "focus"),
            ("Crystal (Arcane Focus)", 1000, "💎", "standard", "", 1, True, "focus"),
            ("Orb (Arcane Focus)", 2000, "🔮", "standard", "", 1, True, "focus"),
            ("Rod (Arcane Focus)", 1000, "🪄", "standard", "", 1, True, "focus"),
            ("Staff (Arcane Focus)", 500, "🪄", "standard", "", 1, True, "focus"),
            ("Wand (Arcane Focus)", 1000, "🪄", "standard", "", 1, True, "focus"),
            # pack: Scholar's pack OR explorer's pack
            ("Scholar's Pack", 4000, "🎒", "standard", "", 1, True, "pack"),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, True, "pack"),
        ],
    },
}

# 2024 D&D Background starting equipment (PHB 2024)
# Choice groups only where the 2024 PHB lets the player pick a variant of an item
# ("same as above" tool/instrument/gaming set). The default is the first line.
# - Artisan: tools (one type of artisan's tools)
# - Entertainer: instrument (one musical instrument)
# - Soldier: gaming_set (one gaming set)
# Other backgrounds have no "or" and get no group.
BACKGROUND_EQUIPMENT = {
    "Acolyte": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Amulet (Holy Symbol)", 500, "✝️", "standard", "", 1, False, ""),
            ("Prayer Book", 500, "📖", "standard", "", 1, False, ""),
            ("Incense (5 sticks)", 10, "🕯️", "trivial", "", 5, False, ""),
            ("Vestments", 500, "👘", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Artisan": {
        "coins_cp": 2000,  # 20 gp
        "items": [
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
            # tools: one type of artisan's tools
            ("Woodcarver's Tools (Artisan's Tools)", 2000, "🔨", "standard", "", 1, True, "tools"),
            ("Brewer's Supplies (Artisan's Tools)", 2000, "🍺", "standard", "", 1, True, "tools"),
            (
                "Calligrapher's Supplies (Artisan's Tools)",
                1000,
                "🖋️",
                "standard",
                "",
                1,
                True,
                "tools",
            ),
            ("Carpenter's Tools (Artisan's Tools)", 1000, "🔨", "standard", "", 1, True, "tools"),
            (
                "Leatherworker's Tools (Artisan's Tools)",
                2000,
                "🔨",
                "standard",
                "",
                1,
                True,
                "tools",
            ),
            ("Mason's Tools (Artisan's Tools)", 2000, "🔨", "standard", "", 1, True, "tools"),
            ("Potter's Tools (Artisan's Tools)", 2000, "🏺", "standard", "", 1, True, "tools"),
            ("Smith's Tools (Artisan's Tools)", 2000, "🔨", "standard", "", 1, True, "tools"),
            ("Tinker's Tools (Artisan's Tools)", 1000, "🔧", "standard", "", 1, True, "tools"),
            ("Weaver's Tools (Artisan's Tools)", 2000, "🧵", "standard", "", 1, True, "tools"),
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
            ("Costume", 500, "🎭", "standard", "", 1, False, ""),
            ("Mirror", 500, "🪞", "standard", "", 1, False, ""),
            # instrument: one musical instrument
            ("Lute (Musical Instrument)", 3500, "🎵", "standard", "", 1, True, "instrument"),
            ("Flute (Musical Instrument)", 200, "🎵", "standard", "", 1, True, "instrument"),
            ("Lyre (Musical Instrument)", 300, "🎵", "standard", "", 1, True, "instrument"),
            ("Horn (Musical Instrument)", 300, "📯", "standard", "", 1, True, "instrument"),
            ("Drum (Musical Instrument)", 600, "🥁", "standard", "", 1, True, "instrument"),
        ],
    },
    "Farmer": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Carpenter's Tools (Artisan's Tools)", 1000, "🔨", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Guard": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Uniform", 500, "👕", "standard", "", 1, False, ""),
            ("Horn (Musical Instrument)", 300, "📯", "standard", "", 1, False, ""),
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
            ("Ink Pen", 2, "🖋️", "trivial", "", 1, False, ""),
            ("Ink (1 oz)", 1000, "🖋️", "trivial", "", 1, False, ""),
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
            ("Calligrapher's Supplies (Artisan's Tools)", 1000, "🖋️", "standard", "", 1, False, ""),
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
        ],
    },
    "Soldier": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Insignia of Rank", 100, "🎖️", "trivial", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
            # gaming_set: one gaming set
            ("Dice (Gaming Set)", 100, "🎲", "trivial", "", 1, True, "gaming_set"),
            ("Playing Cards (Gaming Set)", 100, "🎴", "trivial", "", 1, True, "gaming_set"),
            ("Dragonchess (Gaming Set)", 100, "♟️", "trivial", "", 1, True, "gaming_set"),
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
    packs_configured: int = 0


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
                specs = {
                    "value_cp": value_cp,
                    "symbol": symbol,
                    "rarity": rarity,
                    "magic_type": magic_type,
                }
                # Add stacked fields for ammunition
                if name in STACKED_AMMO_SPECS:
                    _, _, _, _, unit_name, value_units = STACKED_AMMO_SPECS[name]
                    specs["is_stacked"] = True
                    specs["unit_name"] = unit_name
                    specs["value_units"] = value_units
                weight_lb = STARTING_EQUIPMENT_WEIGHTS.get(name)
                if weight_lb is not None:
                    specs["weight_hundredth_lb"] = round(weight_lb * 100)
                item_specs[name] = specs

    # Collect all unique items from background equipment
    for bg_data in BACKGROUND_EQUIPMENT.values():
        for item_data in bg_data["items"]:
            name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
            if name not in item_specs:
                specs = {
                    "value_cp": value_cp,
                    "symbol": symbol,
                    "rarity": rarity,
                    "magic_type": magic_type,
                }
                if name in STACKED_AMMO_SPECS:
                    _, _, _, _, unit_name, value_units = STACKED_AMMO_SPECS[name]
                    specs["is_stacked"] = True
                    specs["unit_name"] = unit_name
                    specs["value_units"] = value_units
                weight_lb = STARTING_EQUIPMENT_WEIGHTS.get(name)
                if weight_lb is not None:
                    specs["weight_hundredth_lb"] = round(weight_lb * 100)
                item_specs[name] = specs

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
        else:
            # Update stacked fields if they were blank on an existing row
            updated = []
            if name in STACKED_AMMO_SPECS:
                _, _, _, _, unit_name, value_units = STACKED_AMMO_SPECS[name]
                if not item.is_stacked:
                    item.is_stacked = True
                    updated.append("is_stacked")
                if not item.unit_name:
                    item.unit_name = unit_name
                    updated.append("unit_name")
                if item.value_units != value_units:
                    item.value_units = value_units
                    updated.append("value_units")
                if updated:
                    item.save(update_fields=updated)

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


def _sync_lines(line_model, entry_field: str, entry, items: list[tuple]) -> None:
    """Make the lines of `entry` match `items` exactly, in order.

    The claim grants the first line (by id) of each choice group, so line order
    matters. If the existing lines have the same (item, is_choice, choice_group)
    sequence in id order, only changed quantities are saved in place. Otherwise
    all lines of the entry are deleted and recreated in data order. This removes
    stale lines, such as an old fixed line that is now a choice default, or a
    renamed item.

    Callers only reach this for a new template or a forced run.
    """
    club = entry.template.club
    desired = [
        (_get_item(club, name).pk, is_choice, choice_group, qty)
        for name, _value, _symbol, _rarity, _magic, qty, is_choice, choice_group in items
    ]
    existing = list(line_model.objects.filter(**{entry_field: entry}).order_by("id"))

    if [(ln.item_id, ln.is_choice, ln.choice_group) for ln in existing] == [d[:3] for d in desired]:
        for line, (_item_id, _is_choice, _group, qty) in zip(existing, desired, strict=True):
            if line.quantity != qty:
                line.quantity = qty
                line.save(update_fields=["quantity"])
        return

    line_model.objects.filter(**{entry_field: entry}).delete()
    line_model.objects.bulk_create(
        line_model(
            **{entry_field: entry},
            item_id=item_id,
            quantity=qty,
            is_choice=is_choice,
            choice_group=choice_group,
        )
        for item_id, is_choice, choice_group, qty in desired
    )


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

        if created or force:
            _sync_lines(StartingEquipmentClassLine, "class_entry", entry, class_data["items"])

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

        if created or force:
            _sync_lines(
                StartingEquipmentBackgroundLine, "background_entry", entry, bg_data["items"]
            )

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
    is False, it returns a summary with `skipped=True` and makes no changes
    to the template/lines. However, pack seeding runs on every run (it is
    idempotent and safe). If `force` is True, existing entries are updated
    to match the default data: coins are overwritten, and each entry's lines
    are made to match the data exactly (stale lines are removed). A forced run
    on a template that already matches writes no lines.

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

        # Items and pack containers are seeded on every run, even when the
        # template is skipped. Both steps are idempotent.
        summary.items_created = _create_items(club)
        try:
            summary.packs_configured = seed_pack_containers(club).configured
        except PackSeedingError as err:
            raise StartingEquipmentSeedError(str(err)) from err

        if not created and not force:
            summary.skipped = True
            return summary

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
