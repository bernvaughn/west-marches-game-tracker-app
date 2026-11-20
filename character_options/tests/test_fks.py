"""Tests for FK relationships."""

import pytest
from django.db.models import ProtectedError

from character_options.models import Background, CharacterClass, Species
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentClassEntry,
    StartingEquipmentTemplate,
)


@pytest.mark.django_db
def test_character_accepts_new_fks(club, species, char_class, background):
    """Character can be created with the new FKs."""
    from accounts.models import Membership, User

    owner = Membership.objects.create(
        user=User.objects.create_user("owner@example.com", password="pw"),
        club=club,
    )
    char = Character.objects.create(
        club=club,
        owner=owner,
        name="Test",
        species_option=species,
        class_option=char_class,
        background_option=background,
    )
    assert char.species_option == species
    assert char.class_option == char_class
    assert char.background_option == background


@pytest.mark.django_db
def test_deleting_option_set_nulls_character_fk(club, species, char_class, background):
    """Deleting an option SET_NULLs the character FK."""
    from accounts.models import Membership, User

    owner = Membership.objects.create(
        user=User.objects.create_user("owner2@example.com", password="pw"),
        club=club,
    )
    char = Character.objects.create(
        club=club,
        owner=owner,
        name="Test",
        species_option=species,
        class_option=char_class,
        background_option=background,
    )

    species.delete()
    char.refresh_from_db()
    assert char.species_option is None

    char_class.delete()
    char.refresh_from_db()
    assert char.class_option is None

    background.delete()
    char.refresh_from_db()
    assert char.background_option is None


@pytest.mark.django_db
def test_deleting_class_option_used_by_entry_raises_protected(club, char_class):
    """Deleting a class option used by an entry raises ProtectedError."""
    template = StartingEquipmentTemplate.objects.create(club=club, name="Test")
    StartingEquipmentClassEntry.objects.create(
        template=template,
        class_option=char_class,
    )

    with pytest.raises(ProtectedError):
        char_class.delete()


@pytest.mark.django_db
def test_deleting_background_option_used_by_entry_raises_protected(club, background):
    """Deleting a background option used by an entry raises ProtectedError."""
    template = StartingEquipmentTemplate.objects.create(club=club, name="Test")
    StartingEquipmentBackgroundEntry.objects.create(
        template=template,
        background_option=background,
    )

    with pytest.raises(ProtectedError):
        background.delete()
