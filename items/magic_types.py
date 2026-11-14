"""Magic item types. Single source of truth for choices and labels."""

from django.db import models

NONE_LABEL = "None (non-magical)"


class MagicType(models.TextChoices):
    ARMOR = "armor", "Armor"
    POTION = "potion", "Potion"
    RING = "ring", "Ring"
    ROD = "rod", "Rod"
    SCROLL = "scroll", "Scroll"
    STAFF = "staff", "Staff"
    WAND = "wand", "Wand"
    WEAPON = "weapon", "Weapon"
    WONDROUS = "wondrous", "Wondrous item"
