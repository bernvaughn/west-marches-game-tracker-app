"""Models for per-club character options: species, classes, backgrounds."""

from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from accounts.scoping import ClubScopedManager


class CharacterOption(models.Model):
    """Abstract base for club-scoped character options."""

    club_path = "club"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)ss",
    )
    name = models.CharField(max_length=60)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        abstract = True
        ordering = ["sort_order", "name"]
        constraints = [
            UniqueConstraint(
                "club",
                Lower("name"),
                name="%(app_label)s_%(class)s_unique_club_name_ci",
            ),
        ]

    def __str__(self):
        return self.name


class Species(CharacterOption):
    """Playable species for a club."""

    class Meta(CharacterOption.Meta):
        verbose_name_plural = "Species"


class CharacterClass(CharacterOption):
    """Character classes for a club."""

    class Meta(CharacterOption.Meta):
        pass


class Background(CharacterOption):
    """Character backgrounds for a club."""

    class Meta(CharacterOption.Meta):
        pass
