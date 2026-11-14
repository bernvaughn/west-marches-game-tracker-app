from django.db import models

from accounts.scoping import ClubScopedManager

from .magic_types import MagicType
from .rarity import GROUPS


class Item(models.Model):
    club_path = "club"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200)
    symbol = models.CharField(max_length=8, blank=True)
    description = models.TextField(blank=True)
    traits = models.TextField(blank=True)
    details = models.TextField(blank=True)
    rarity = models.CharField(max_length=16, choices=GROUPS, blank=True)
    magic_type = models.CharField(max_length=16, choices=MagicType.choices, blank=True)
    value_cp = models.PositiveIntegerField(default=0)
    retired = models.BooleanField(default=False)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
