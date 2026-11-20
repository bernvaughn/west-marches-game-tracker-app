"""Registry of character option kinds for shared admin logic."""

from django.http import Http404

from character_options.models import Background, CharacterClass, Species
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentClassEntry,
)


class OptionKind:
    """Configuration for one option kind (species, class, background)."""

    def __init__(
        self,
        slug,
        model,
        singular,
        plural,
        character_fk_field,
        character_reverse_field,
        character_text_field,
        entry_model=None,
        entry_fk_field=None,
        entry_reverse_field=None,
        entry_text_field=None,
    ):
        self.slug = slug
        self.model = model
        self.singular = singular
        self.plural = plural
        self.character_fk_field = character_fk_field
        self.character_reverse_field = character_reverse_field
        self.character_text_field = character_text_field
        self.entry_model = entry_model
        self.entry_fk_field = entry_fk_field
        self.entry_reverse_field = entry_reverse_field
        self.entry_text_field = entry_text_field


KINDS = {
    "species": OptionKind(
        slug="species",
        model=Species,
        singular="Species",
        plural="Species",
        character_fk_field="species_option",  # Character.species_option
        character_reverse_field="characters",  # Species.characters
        character_text_field="species",
        entry_model=None,
        entry_fk_field=None,
        entry_reverse_field=None,
        entry_text_field=None,
    ),
    "classes": OptionKind(
        slug="classes",
        model=CharacterClass,
        singular="Class",
        plural="Classes",
        character_fk_field="class_option",  # Character.class_option
        character_reverse_field="characters",  # CharacterClass.characters
        character_text_field="char_class",
        entry_model=StartingEquipmentClassEntry,
        entry_fk_field="class_option",  # StartingEquipmentClassEntry.class_option
        entry_reverse_field="starting_entries",  # CharacterClass.starting_entries
        entry_text_field="char_class",
    ),
    "backgrounds": OptionKind(
        slug="backgrounds",
        model=Background,
        singular="Background",
        plural="Backgrounds",
        character_fk_field="background_option",  # Character.background_option
        character_reverse_field="characters",  # Background.characters
        character_text_field="background",
        entry_model=StartingEquipmentBackgroundEntry,
        entry_fk_field="background_option",  # StartingEquipmentBackgroundEntry.background_option
        entry_reverse_field="starting_entries",  # Background.starting_entries
        entry_text_field="background",
    ),
}


def get_kind(slug):
    """Return the OptionKind for a slug, or raise Http404."""
    try:
        return KINDS[slug]
    except KeyError as err:
        raise Http404(f"Unknown option kind: {slug}") from err
