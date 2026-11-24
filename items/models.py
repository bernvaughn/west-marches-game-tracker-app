from django.db import models
from django.db.models import Q

from accounts.scoping import ClubScopedManager
from ledger.models import AppendOnlyManager, AppendOnlyModel, LedgerEntry

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
    gm_details = models.TextField(
        blank=True,
        verbose_name="GM-only details",
        help_text=(
            "Only game masters and club admins see this. Use it for secrets, such as a curse."
        ),
    )
    rarity = models.CharField(max_length=16, choices=GROUPS, blank=True)
    magic_type = models.CharField(max_length=16, choices=MagicType.choices, blank=True)
    value_cp = models.PositiveIntegerField(default=0)
    retired = models.BooleanField(default=False)
    is_container = models.BooleanField(default=False)
    is_stacked = models.BooleanField(default=False)
    unit_name = models.CharField(max_length=40, blank=True)
    value_units = models.PositiveIntegerField(default=1)
    weight_hundredth_lb = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Weight of one unit in hundredths of a pound. Leave blank if unknown.",
    )

    objects = ClubScopedManager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(is_stacked=True, is_container=True),
                name="item_not_stacked_and_container",
            ),
            models.CheckConstraint(
                condition=Q(value_units__gte=1),
                name="item_value_units_ge_1",
            ),
            models.CheckConstraint(
                condition=Q(is_stacked=False) | ~Q(unit_name=""),
                name="item_stacked_needs_unit_name",
            ),
        ]

    def __str__(self):
        return self.name


class ContainerSlot(models.Model):
    club_path = "container__club"

    container = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="slots")
    chance_pct = models.PositiveSmallIntegerField(default=100)
    unknown = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(chance_pct__gte=1, chance_pct__lte=100),
                name="container_slot_chance_pct_1_100",
            ),
        ]

    def __str__(self):
        return f"Slot {self.position} on {self.container.name}"


class ContainerSlotOption(models.Model):
    club_path = "slot__container__club"

    slot = models.ForeignKey(ContainerSlot, on_delete=models.CASCADE, related_name="options")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="container_option_uses")
    qty_min = models.PositiveIntegerField(default=1)
    qty_max = models.PositiveIntegerField(default=1)
    weight = models.PositiveIntegerField(default=1)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(qty_min__gte=1),
                name="container_slot_option_qty_min_ge_1",
            ),
            models.CheckConstraint(
                condition=Q(qty_max__gte=models.F("qty_min")),
                name="container_slot_option_qty_max_gte_qty_min",
            ),
            models.CheckConstraint(
                condition=Q(weight__gte=1),
                name="container_slot_option_weight_ge_1",
            ),
        ]

    def __str__(self):
        return f"{self.item.name} x{self.qty_min}-{self.qty_max} on slot {self.slot_id}"


class ContainerOpening(AppendOnlyModel):
    club_path = "character__club"

    objects = AppendOnlyManager()

    entry = models.OneToOneField(LedgerEntry, on_delete=models.PROTECT, related_name="opening")
    container = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="openings")
    character = models.ForeignKey("player_characters.Character", on_delete=models.PROTECT)
    result = models.JSONField(default=list)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Opening of {self.container} for {self.character}"
