"""Models for player-written inventory items and their history."""

import re

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.scoping import ClubScopedQuerySet
from ledger.models import AppendOnlyManager, AppendOnlyModel
from player_items.rules import character_can_change_items

# Maximum player-written items per character
MAX_ITEMS_PER_CHARACTER = 50


def normalize_name_key(name: str) -> str:
    """Normalize a name to a key for grouping and searching.

    Lowercases and collapses whitespace to single spaces.
    """
    return re.sub(r"\s+", " ", name.strip().lower())


class PlayerItemQuerySet(ClubScopedQuerySet):
    pass


PlayerItemManager = models.Manager.from_queryset(PlayerItemQuerySet)


class PlayerItem(models.Model):
    """A player-written inventory entry. Not in the ledger; free text with quantity."""

    club_path = "club"

    class Review(models.TextChoices):
        OPEN = "open", "Open"
        LEFT_AS_IS = "left_as_is", "Left as is"
        RESOLVED = "resolved", "Resolved"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="player_items")
    character = models.ForeignKey(
        "player_characters.Character",
        on_delete=models.CASCADE,
        related_name="player_items",
    )
    name = models.CharField(max_length=80)
    name_key = models.CharField(max_length=80, db_index=True)
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Whole number, at least 1.",
    )
    note = models.TextField(blank=True)
    review = models.CharField(
        max_length=16,
        choices=Review.choices,
        default=Review.OPEN,
    )
    resolved_by_change = models.ForeignKey(
        "PlayerItemChange",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_items",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = PlayerItemManager()

    class Meta:
        ordering = ["name_key", "name"]
        indexes = [
            models.Index(fields=["club", "character", "name_key"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="player_item_name_not_empty",
            ),
        ]

    def __str__(self):
        return f"{self.character}: {self.name} x{self.quantity}"

    def clean(self):
        if not character_can_change_items(self.character):
            raise ValidationError("This character cannot change items.")

    def save(self, *args, **kwargs):  # noqa: DJ012
        self.name_key = normalize_name_key(self.name)
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            # Enforce 50-row limit per character on new rows
            count = PlayerItem.objects.for_club(self.club).filter(character=self.character).count()
            if count > MAX_ITEMS_PER_CHARACTER:
                # Delete the row we just created and raise
                super().delete()
                msg = (
                    f"Cannot have more than {MAX_ITEMS_PER_CHARACTER} "
                    "player-written items per character."
                )
                raise ValidationError(msg)

    def delete(self, *args, **kwargs):
        if not character_can_change_items(self.character):
            raise ValidationError("This character cannot change items.")
        super().delete(*args, **kwargs)


class PlayerItemChange(AppendOnlyModel):
    """Append-only history of every add, edit, remove, promote, merge, or match."""

    club_path = "club"

    class Kind(models.TextChoices):
        ADDED = "added", "Added"
        EDITED = "edited", "Edited"
        REMOVED = "removed", "Removed"
        PROMOTED = "promoted", "Promoted"
        MERGED = "merged", "Merged"
        MATCHED = "matched", "Matched"

    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="player_item_changes"
    )
    character = models.ForeignKey(
        "player_characters.Character",
        on_delete=models.PROTECT,
        related_name="player_item_changes",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    old_name = models.CharField(max_length=80, blank=True)
    new_name = models.CharField(max_length=80, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    item = models.ForeignKey(
        "items.Item",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="player_item_changes",
    )
    by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="player_item_changes",
    )
    at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)

    objects = AppendOnlyManager()

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [
            models.Index(fields=["club", "character", "-at"]),
        ]

    def __str__(self):
        return f"{self.character} {self.kind} at {self.at}"


class PlayerNoticeQuerySet(ClubScopedQuerySet):
    pass


PlayerNoticeManager = models.Manager.from_queryset(PlayerNoticeQuerySet)


class PlayerNotice(models.Model):
    """A notice for a membership (player) about item resolution."""

    club_path = "membership__club"

    class Kind(models.TextChoices):
        ITEM_PROMOTED = "item_promoted", "Item promoted"
        ITEM_MERGED = "item_merged", "Item merged"
        ITEM_MATCHED = "item_matched", "Item matched"
        GENERIC = "generic", "Generic"

    membership = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.CASCADE,
        related_name="player_notices",
    )
    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="player_notices"
    )
    character = models.ForeignKey(
        "player_characters.Character",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="player_notices",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    text = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    objects = PlayerNoticeManager()

    class Meta:
        ordering = ["-created", "-id"]
        indexes = [
            models.Index(fields=["membership", "-created"]),
        ]

    def __str__(self):
        return f"Notice for {self.membership}: {self.kind}"

    def dismiss(self):
        if self.dismissed_at is None:
            self.dismissed_at = timezone.now()
            self.save(update_fields=["dismissed_at"])
