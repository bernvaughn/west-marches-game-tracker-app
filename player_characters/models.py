from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.scoping import ClubScopedManager, ClubScopedQuerySet
from ledger.models import AppendOnlyManager, AppendOnlyModel

ABILITIES = [
    ("strength", "STR", "Strength"),
    ("dexterity", "DEX", "Dexterity"),
    ("constitution", "CON", "Constitution"),
    ("intelligence", "INT", "Intelligence"),
    ("wisdom", "WIS", "Wisdom"),
    ("charisma", "CHA", "Charisma"),
]


OTHER = "Other"

PRONOUNS_CHOICES = [
    ("he/him", "he/him"),
    ("she/her", "she/her"),
    ("they/them", "they/them"),
]

ALIGNMENT_CHOICES = [
    ("Chaotic Evil", "Chaotic Evil"),
    ("Chaotic Good", "Chaotic Good"),
    ("Chaotic Neutral", "Chaotic Neutral"),
    ("Lawful Evil", "Lawful Evil"),
    ("Lawful Good", "Lawful Good"),
    ("Lawful Neutral", "Lawful Neutral"),
    ("Neutral Evil", "Neutral Evil"),
    ("Neutral Good", "Neutral Good"),
    ("True Neutral", "True Neutral"),
]


def _ability_field():
    return models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="Optional. Whole number from 1 to 30.",
    )


class CharacterQuerySet(ClubScopedQuerySet):
    def not_archived(self):
        """Characters that are not archived."""
        return self.filter(archived_at__isnull=True)

    def living(self):
        """Characters that are not dead (regardless of archive state)."""
        return self.filter(died_on__isnull=True)

    def dead(self):
        """Characters that are dead (regardless of archive state)."""
        return self.filter(died_on__isnull=False)


CharacterManager = models.Manager.from_queryset(CharacterQuerySet)


class Character(models.Model):
    club_path = "club"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="characters")
    owner = models.ForeignKey(
        "accounts.Membership", on_delete=models.PROTECT, related_name="characters"
    )
    name = models.CharField(max_length=200)
    level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Optional. Whole number from 1.",
    )
    char_class = models.CharField("Class", max_length=60, blank=True)
    species = models.CharField(max_length=60, blank=True)
    background = models.CharField(
        max_length=60,
        blank=True,
        help_text="Character background (e.g., Acolyte, Soldier)",
    )
    species_option = models.ForeignKey(
        "character_options.Species",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="characters",
    )
    class_option = models.ForeignKey(
        "character_options.CharacterClass",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="characters",
    )
    background_option = models.ForeignKey(
        "character_options.Background",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="characters",
    )
    alignment = models.CharField(max_length=60, blank=True)
    pronouns = models.CharField(max_length=60, blank=True)
    strength = _ability_field()
    dexterity = _ability_field()
    constitution = _ability_field()
    intelligence = _ability_field()
    wisdom = _ability_field()
    charisma = _ability_field()
    armor_class = models.PositiveSmallIntegerField(
        "AC",
        null=True,
        blank=True,
        validators=[MaxValueValidator(40)],
        help_text="Optional. Whole number from 0 to 40.",
    )
    max_hp = models.PositiveIntegerField(
        "Max HP",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Optional. Whole number from 1.",
    )
    perception_bonus = models.SmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-20), MaxValueValidator(30)],
        help_text="Optional. May be negative. Passive Perception is 10 plus this.",
    )
    xp = models.PositiveIntegerField("XP", null=True, blank=True)
    description = models.TextField(blank=True)
    shop_open = models.BooleanField(default=False)
    starting_equipment_claimed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    last_printed_at = models.DateTimeField(null=True, blank=True)
    # Death and archive
    died_on = models.DateField(null=True, blank=True)
    death_note = models.TextField(blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = CharacterManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.owner_id and self.owner.club_id != self.club_id:
            raise ValidationError("Owner must be a member of the character's club.")

    @property
    def is_dead(self):
        return self.died_on is not None

    @property
    def is_archived(self):
        return self.archived_at is not None

    @property
    def is_active(self):
        return self.archived_at is None


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


class ItemNote(models.Model):
    """A player's private note on one item in their character's inventory.

    One row per character and item, never per unit in a stack. The row is kept
    when the item leaves the inventory, so the note hides and returns with the
    item. Never touches the ledger or the item catalogue.
    """

    club_path = "character__club"

    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name="item_notes")
    item = models.ForeignKey("items.Item", on_delete=models.CASCADE, related_name="+")
    text = models.TextField(max_length=1000)

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["character", "item"], name="unique_item_note_per_item"),
            models.CheckConstraint(condition=~models.Q(text=""), name="item_note_text_non_empty"),
        ]

    def __str__(self):
        return f"{self.character}: note on {self.item}"


class CharacterStatusChange(AppendOnlyModel):
    """Append-only history of a character's death/archive state changes."""

    club_path = "character__club"

    class Kind(models.TextChoices):
        DIED = "died", "Died"
        REVIVED = "revived", "Revived"
        ARCHIVED = "archived", "Archived"
        UNARCHIVED = "unarchived", "Unarchived"

    character = models.ForeignKey(
        Character, on_delete=models.PROTECT, related_name="status_changes"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    by = models.ForeignKey(
        "accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)
    date = models.DateField(default=timezone.localdate)

    objects = AppendOnlyManager()

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [
            models.Index(fields=["character", "at"]),
        ]

    def __str__(self):
        return f"{self.character} {self.kind} at {self.at}"
