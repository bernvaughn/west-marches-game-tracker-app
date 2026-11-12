from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from accounts.scoping import ClubScopedManager


class Character(models.Model):
    club_path = "club"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="characters")
    owner = models.ForeignKey(
        "accounts.Membership", on_delete=models.PROTECT, related_name="characters"
    )
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    stats = models.TextField(blank=True)
    details = models.TextField(blank=True)
    level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Optional. Whole number from 1.",
    )
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.owner_id and self.owner.club_id != self.club_id:
            raise ValidationError("Owner must be a member of the character's club.")


class Trade(models.Model):
    club_path = "club"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ACCEPTED = "accepted", "Accepted"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="trades")
    sender = models.ForeignKey(Character, on_delete=models.CASCADE, related_name="trades_sent")
    receiver = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="trades_received"
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.REQUESTED)
    note = models.TextField(blank=True)
    sender_approved = models.BooleanField(default=False)
    receiver_approved = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Trade {self.pk}: {self.sender} -> {self.receiver}"


class TradeLine(models.Model):
    club_path = "trade__club"

    trade = models.ForeignKey(Trade, on_delete=models.CASCADE, related_name="lines")
    from_sender = models.BooleanField(default=True)
    item = models.ForeignKey("items.Item", null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)
    coins = models.IntegerField(default=0)

    objects = ClubScopedManager()

    def __str__(self):
        return f"TradeLine {self.pk} of trade {self.trade_id}"


class SelectedCharacter(models.Model):
    """The character a member is acting as in a club (one row per membership)."""

    club_path = "membership__club"

    membership = models.OneToOneField(
        "accounts.Membership", on_delete=models.CASCADE, related_name="selected_character"
    )
    character = models.ForeignKey(
        Character, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ClubScopedManager()

    def __str__(self):
        return f"{self.membership} acts as {self.character}"


class JunkMark(models.Model):
    """Items a character set aside to sell. Capped on read; never touches the ledger."""

    club_path = "character__club"

    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name="junk_marks")
    item = models.ForeignKey("items.Item", on_delete=models.CASCADE, related_name="junk_marks")
    quantity = models.PositiveIntegerField()

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["character", "item"], name="unique_junk_per_item"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="junk_quantity_min"),
        ]

    def __str__(self):
        return f"{self.character}: {self.quantity} × {self.item} junk"
