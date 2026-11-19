"""Services for character options: seeding, matching, and admin operations."""

from django.db import transaction
from django.db.models import Count, Max, Q, Value

from character_options.defaults import (
    DEFAULT_BACKGROUNDS,
    DEFAULT_CLASSES,
    DEFAULT_SPECIES,
)
from character_options.kinds import KINDS
from character_options.models import Background, CharacterClass, Species
from player_characters.models import Character


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


# --- Admin services ---


def active_options(club, model):
    """Return active records for a club, ordered by sort_order then name.

    Pickers (character form, equipment entries) should use this.

    Args:
        club: An accounts.Club instance.
        model: One of Species, CharacterClass, Background.

    Returns:
        QuerySet of active records.
    """
    return model.objects.for_club(club).filter(is_active=True).order_by("sort_order", "name")


def annotate_usage(qs, kind_slug):
    """Annotate a queryset with character_count and entry_count.

    Args:
        qs: QuerySet of option records (Species, CharacterClass, or Background).
        kind_slug: One of 'species', 'classes', 'backgrounds'.

    Returns:
        QuerySet annotated with character_count and entry_count.
    """
    kind = KINDS[kind_slug]
    annotations = {
        "character_count": Count(
            kind.character_reverse_field,
            filter=Q(**{f"{kind.character_reverse_field}__isnull": False}),
        ),
    }
    if kind.entry_model:
        annotations["entry_count"] = Count(
            kind.entry_reverse_field,
            filter=Q(**{f"{kind.entry_reverse_field}__isnull": False}),
        )
    else:
        annotations["entry_count"] = Value(0)
    return qs.annotate(**annotations)


def usage(kind_slug, option):
    """Return (character_count, entry_count) for a single option.

    Args:
        kind_slug: One of 'species', 'classes', 'backgrounds'.
        option: An instance of the option model.

    Returns:
        Tuple of (character_count, entry_count).
    """
    qs = annotate_usage(option.__class__.objects.filter(pk=option.pk), kind_slug)
    result = qs.first()
    return result.character_count, result.entry_count


def delete_blockers(kind_slug, option):
    """Check if an option can be deleted.

    Returns a message string if blocked, or None if it can be deleted.

    Args:
        kind_slug: One of 'species', 'classes', 'backgrounds'.
        option: An instance of the option model.

    Returns:
        Blocking message string, or None.
    """
    char_count, entry_count = usage(kind_slug, option)
    parts = []
    if char_count:
        parts.append(f"{char_count} character{'s' if char_count != 1 else ''}")
    if entry_count:
        parts.append(f"{entry_count} starting equipment entr{'y' if entry_count == 1 else 'ies'}")
    if parts:
        return f"Used by {', '.join(parts)}. Archive it instead."
    return None


@transaction.atomic
def rename_option(kind_slug, option, new_name):
    """Rename an option and update linked display text.

    Updates the option name, then updates the text snapshot on linked
    Character rows and starting equipment entries (the text fields
    always hold the display name; matching is by FK only).

    Args:
        kind_slug: One of 'species', 'classes', 'backgrounds'.
        option: An instance of the option model.
        new_name: The new name (already validated as unique).

    Returns:
        The updated option instance.
    """
    kind = KINDS[kind_slug]
    old_name = option.name
    if old_name == new_name:
        return option

    option.name = new_name
    option.save(update_fields=["name"])

    # Update Character text field (filter by forward FK on Character)
    Character.objects.filter(**{kind.character_fk_field: option}).update(
        **{kind.character_text_field: new_name}
    )

    # Update starting equipment entry text field (filter by forward FK on entry model)
    if kind.entry_model:
        kind.entry_model.objects.filter(**{kind.entry_fk_field: option}).update(
            **{kind.entry_text_field: new_name}
        )

    return option


def move_option(option, direction):
    """Move an option up or down in the club's ordering.

    Renumbers all records of that kind in the club to 10, 20, 30...
    in current order, then swaps with the neighbour.

    Args:
        option: The option instance to move.
        direction: 'up' or 'down'.

    Returns:
        The moved option instance (with updated sort_order).
    """
    model = option.__class__
    club = option.club
    # Get all records for this club and kind, ordered
    records = list(model.objects.for_club(club).order_by("sort_order", "name"))
    # Renumber to 10, 20, 30...
    for idx, rec in enumerate(records):
        rec.sort_order = (idx + 1) * 10
    model.objects.bulk_update(records, ["sort_order"])

    # Find the option again (now renumbered) and swap
    records = list(model.objects.for_club(club).order_by("sort_order", "name"))
    current_idx = next(i for i, r in enumerate(records) if r.pk == option.pk)

    if direction == "up" and current_idx > 0:
        target_idx = current_idx - 1
    elif direction == "down" and current_idx < len(records) - 1:
        target_idx = current_idx + 1
    else:
        return option  # No-op at boundaries

    # Swap sort_order values
    records[current_idx].sort_order, records[target_idx].sort_order = (
        records[target_idx].sort_order,
        records[current_idx].sort_order,
    )
    model.objects.bulk_update([records[current_idx], records[target_idx]], ["sort_order"])
    option.refresh_from_db()
    return option


def create_option(kind_slug, club, name):
    """Create a new option with sort_order = max + 10.

    Args:
        kind_slug: One of 'species', 'classes', 'backgrounds'.
        club: An accounts.Club instance.
        name: The option name (already validated).

    Returns:
        The created option instance.
    """
    kind = KINDS[kind_slug]
    max_order = (
        kind.model.objects.for_club(club).aggregate(max_order=Max("sort_order"))["max_order"] or 0
    )
    return kind.model.objects.create(club=club, name=name, sort_order=max_order + 10)
