from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.scoping import ClubScopedManager


class StartingEquipmentTemplate(models.Model):
    """Club-level template for starting equipment by class/background/level."""

    club_path = "club"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="starting_templates",
    )
    name = models.CharField(max_length=100)  # e.g., "2024 D&D Default", "Low Magic", "High Fantasy"
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = ClubScopedManager()

    class Meta:
        unique_together = ["club", "name"]
        ordering = ["name"]
        indexes = [
            models.Index(fields=["club", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.club})"


class StartingEquipmentClassEntry(models.Model):
    """Equipment granted for a specific class at a level range."""

    club_path = "template__club"

    template = models.ForeignKey(
        StartingEquipmentTemplate,
        on_delete=models.CASCADE,
        related_name="class_entries",
    )
    class_option = models.ForeignKey(
        "character_options.CharacterClass",
        null=False,
        blank=False,
        on_delete=models.PROTECT,
        related_name="starting_entries",
    )
    min_level = models.PositiveSmallIntegerField(default=1)
    max_level = models.PositiveSmallIntegerField(default=20)
    coins_cp = models.PositiveIntegerField(default=0)  # Base coins for this class

    objects = ClubScopedManager()

    class Meta:
        ordering = ["class_option__name", "min_level"]
        indexes = [
            models.Index(fields=["template", "class_option"]),
            models.Index(fields=["template", "min_level", "max_level"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(min_level__lte=models.F("max_level")),
                name="class_entry_min_level_lte_max_level",
            ),
            models.CheckConstraint(
                check=models.Q(min_level__gte=1) & models.Q(max_level__lte=20),
                name="class_entry_level_range",
            ),
        ]

    def __str__(self):
        return f"{self.class_option.name} L{self.min_level}-{self.max_level} ({self.template})"


class StartingEquipmentClassLine(models.Model):
    """Individual item in a class starting package."""

    club_path = "class_entry__template__club"

    class_entry = models.ForeignKey(
        StartingEquipmentClassEntry,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    is_choice = models.BooleanField(default=False)  # If true, player picks one from a group
    choice_group = models.CharField(max_length=50, blank=True)  # Groups mutually exclusive choices

    objects = ClubScopedManager()

    class Meta:
        ordering = ["class_entry", "choice_group", "id"]
        indexes = [
            models.Index(fields=["class_entry", "is_choice", "choice_group"]),
        ]

    def __str__(self):
        choice_info = f" (choice: {self.choice_group})" if self.is_choice else ""
        return f"{self.quantity}× {self.item}{choice_info}"


class StartingEquipmentBackgroundEntry(models.Model):
    """Equipment granted for a specific background."""

    club_path = "template__club"

    template = models.ForeignKey(
        StartingEquipmentTemplate,
        on_delete=models.CASCADE,
        related_name="background_entries",
    )
    background_option = models.ForeignKey(
        "character_options.Background",
        null=False,
        blank=False,
        on_delete=models.PROTECT,
        related_name="starting_entries",
    )
    coins_cp = models.PositiveIntegerField(default=0)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["background_option__name"]
        indexes = [
            models.Index(fields=["template", "background_option"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "background_option"],
                name="unique_background_per_template",
            ),
        ]

    def __str__(self):
        return f"{self.background_option.name} ({self.template})"


class StartingEquipmentBackgroundLine(models.Model):
    """Individual item in a background starting package."""

    club_path = "background_entry__template__club"

    background_entry = models.ForeignKey(
        StartingEquipmentBackgroundEntry,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    is_choice = models.BooleanField(default=False)
    choice_group = models.CharField(max_length=50, blank=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["background_entry", "choice_group", "id"]
        indexes = [
            models.Index(fields=["background_entry", "is_choice", "choice_group"]),
        ]

    def __str__(self):
        choice_info = f" (choice: {self.choice_group})" if self.is_choice else ""
        return f"{self.quantity}× {self.item}{choice_info}"


class StartingEquipmentLevelCoins(models.Model):
    """Coins by character level (for levels > 1). Based on 2024 DMG table."""

    club_path = "template__club"

    template = models.ForeignKey(
        StartingEquipmentTemplate,
        on_delete=models.CASCADE,
        related_name="level_coins",
    )
    level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(20)]
    )
    coins_cp = models.PositiveIntegerField()  # Total starting coins at this level

    objects = ClubScopedManager()

    class Meta:
        ordering = ["level"]
        indexes = [
            models.Index(fields=["template", "level"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "level"],
                name="unique_level_coins_per_template",
            ),
        ]

    def __str__(self):
        return f"Level {self.level}: {self.coins_cp} cp ({self.template})"


class MagicItemStartingOption(models.Model):
    """Magic items admins mark as available for starting equipment requests."""

    club_path = "template__club"

    template = models.ForeignKey(
        StartingEquipmentTemplate,
        on_delete=models.CASCADE,
        related_name="magic_options",
    )
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    max_per_character = models.PositiveSmallIntegerField(default=1)
    notes = models.TextField(blank=True)  # Admin guidance, e.g., "Level 5+ only"

    objects = ClubScopedManager()

    class Meta:
        ordering = ["item__name"]
        indexes = [
            models.Index(fields=["template", "item"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "item"],
                name="unique_magic_option_per_template",
            ),
        ]

    def __str__(self):
        return f"{self.item} (max {self.max_per_character})"


class StartingEquipmentRequest(models.Model):
    """Player request for a magic starting item."""

    club_path = "club"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="starting_requests",
    )
    character = models.ForeignKey(
        "player_characters.Character",
        on_delete=models.CASCADE,
        related_name="starting_requests",
    )
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    note = models.TextField(blank=True)  # Player's reasoning
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    decided_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    message = models.ForeignKey(
        "accounts.Message",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="starting_request",
    )
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["club", "status"]),
            models.Index(fields=["character", "status"]),
            models.Index(fields=["club", "character", "status"]),
        ]

    def __str__(self):
        return f"{self.character} requests {self.item} ({self.get_status_display()})"
