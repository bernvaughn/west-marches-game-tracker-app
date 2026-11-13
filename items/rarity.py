"""Item bands: magic rarities and everyday-goods price bands. Single source of truth.

Ranges are stored in copper (cp). Special has no range.
"""

from django.db import models


class Rarity(models.TextChoices):
    COMMON = "common", "Common"
    UNCOMMON = "uncommon", "Uncommon"
    RARE = "rare", "Rare"
    VERY_RARE = "very_rare", "Very rare"
    LEGENDARY = "legendary", "Legendary"
    TRIVIAL = "trivial", "Trivial"
    CHEAP = "cheap", "Cheap"
    STANDARD = "standard", "Standard"
    FINE = "fine", "Fine"
    LUXURY = "luxury", "Luxury"
    EXOTIC = "exotic", "Exotic"
    SPECIAL = "special", "Special"


MAGIC = [Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE, Rarity.VERY_RARE, Rarity.LEGENDARY]
EVERYDAY = [
    Rarity.TRIVIAL,
    Rarity.CHEAP,
    Rarity.STANDARD,
    Rarity.FINE,
    Rarity.LUXURY,
    Rarity.EXOTIC,
]
SPECIAL = [Rarity.SPECIAL]

# Django grouped choices.
GROUPS = [
    ("Magic items", [(r.value, r.label) for r in MAGIC]),
    ("Everyday goods", [(r.value, r.label) for r in EVERYDAY]),
    ("Special", [(r.value, r.label) for r in SPECIAL]),
]

# key -> (low_cp, high_cp or None, range text, examples)
BANDS = {
    Rarity.COMMON: (5000, 10000, "50–100 gp", ()),
    Rarity.UNCOMMON: (10100, 50000, "101–500 gp", ()),
    Rarity.RARE: (50100, 500000, "501–5,000 gp", ()),
    Rarity.VERY_RARE: (500100, 5000000, "5,001–50,000 gp", ()),
    Rarity.LEGENDARY: (5000100, None, "50,001 gp and up", ()),
    Rarity.TRIVIAL: (1, 9, "1–9 cp", ("a loaf of bread", "a torch")),
    Rarity.CHEAP: (10, 90, "1–9 sp", ("a day's rations", "a waterskin")),
    Rarity.STANDARD: (100, 1000, "1–10 gp", ("a rope", "a shovel")),
    Rarity.FINE: (1100, 10000, "11–100 gp", ("a longsword", "a riding horse")),
    Rarity.LUXURY: (10100, 100000, "101–1,000 gp", ("a fine carriage", "a small boat")),
    Rarity.EXOTIC: (100100, None, "1,001 gp and up", ("plate armour", "a warship")),
}


def range_label(key):
    """Range text for a band; empty for Special or an unknown key."""
    band = BANDS.get(key)
    return band[2] if band else ""


def examples(key):
    band = BANDS.get(key)
    return ", ".join(band[3]) if band else ""


def ranges():
    """[(key, name, range_text, examples_text)] for every band that has a range."""
    return [(r.value, r.label, range_label(r), examples(r)) for r in Rarity if r in BANDS]
