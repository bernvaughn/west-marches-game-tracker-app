"""2014 DMG rarity value ranges. Single source of truth (gp)."""

from django.db import models


class Rarity(models.TextChoices):
    COMMON = "common", "Common"
    UNCOMMON = "uncommon", "Uncommon"
    RARE = "rare", "Rare"
    VERY_RARE = "very_rare", "Very rare"
    LEGENDARY = "legendary", "Legendary"


RANGES_GP = {
    Rarity.COMMON: (50, 100),
    Rarity.UNCOMMON: (101, 500),
    Rarity.RARE: (501, 5000),
    Rarity.VERY_RARE: (5001, 50000),
    Rarity.LEGENDARY: (50001, None),
}


def range_label(key):
    low, high = RANGES_GP[Rarity(key)]
    if high is None:
        return f"{low:,} gp and up"
    return f"{low:,}–{high:,} gp"


def ranges():
    """[(key, name, range_text)] in choice order."""
    return [(r.value, r.label, range_label(r)) for r in Rarity]
