"""Services for character options: seeding and matching."""

from character_options.defaults import (
    DEFAULT_BACKGROUNDS,
    DEFAULT_CLASSES,
    DEFAULT_SPECIES,
)
from character_options.models import Background, CharacterClass, Species


def seed_default_options(club):
    """Create default species, classes, and backgrounds for a club.

    Idempotent: existing records (by case-insensitive name) are never modified.
    An admin may have renamed, archived, or reordered them — we respect that.

    Args:
        club: An accounts.Club instance.

    Returns:
        dict: Counts of created records per kind, e.g.
            {"species": 11, "classes": 12, "backgrounds": 16}
    """
    created_counts = {}

    for model, defaults, key in [
        (Species, DEFAULT_SPECIES, "species"),
        (CharacterClass, DEFAULT_CLASSES, "classes"),
        (Background, DEFAULT_BACKGROUNDS, "backgrounds"),
    ]:
        # Find existing names case-insensitively
        existing_names = set(model.objects.for_club(club).values_list("name", flat=True))
        existing_lower = {n.lower() for n in existing_names}

        # Build only the missing ones
        to_create = [
            model(club=club, name=name, sort_order=idx * 10)
            for idx, name in enumerate(defaults)
            if name.lower() not in existing_lower
        ]

        if to_create:
            model.objects.bulk_create(to_create)
        created_counts[key] = len(to_create)

    return created_counts


def match_option(club, model, text):
    """Match a club-scoped option by trimmed, case-insensitive name.

    Includes archived (is_active=False) records, because matching is about
    identity and archived records stay valid on existing characters.

    Args:
        club: An accounts.Club instance.
        model: One of Species, CharacterClass, Background.
        text: The input text to match.

    Returns:
        The matching model instance, or None if text is empty/whitespace
        or no match is found in this club.
    """
    if not text or not text.strip():
        return None
    cleaned = text.strip()
    return model.objects.for_club(club).filter(name__iexact=cleaned).first()
