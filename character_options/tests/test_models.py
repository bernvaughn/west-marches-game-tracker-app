"""Tests for character option models."""

import pytest
from django.db import IntegrityError, transaction

from character_options.models import Background, CharacterClass, Species


@pytest.mark.django_db
def test_unique_per_club_case_insensitive(club):
    """Creating 'fighter' when 'Fighter' exists raises IntegrityError."""
    CharacterClass.objects.create(club=club, name="Fighter")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CharacterClass.objects.create(club=club, name="fighter")


@pytest.mark.django_db
def test_same_name_allowed_in_another_club(club, other_club):
    """Same name is allowed in a different club."""
    CharacterClass.objects.create(club=club, name="Fighter")
    CharacterClass.objects.create(club=other_club, name="Fighter")

    assert CharacterClass.objects.for_club(club).count() == 1
    assert CharacterClass.objects.for_club(other_club).count() == 1


@pytest.mark.django_db
def test_same_name_allowed_across_kinds(club):
    """Same name is allowed across Species, CharacterClass, Background."""
    Species.objects.create(club=club, name="Fighter")
    CharacterClass.objects.create(club=club, name="Fighter")
    Background.objects.create(club=club, name="Fighter")

    assert Species.objects.for_club(club).count() == 1
    assert CharacterClass.objects.for_club(club).count() == 1
    assert Background.objects.for_club(club).count() == 1


@pytest.mark.django_db
def test_defaults_ordering_by_sort_order(club):
    """Records order by sort_order then name."""
    Species.objects.create(club=club, name="Zebra", sort_order=0)
    Species.objects.create(club=club, name="Alpha", sort_order=10)
    Species.objects.create(club=club, name="Beta", sort_order=10)

    names = list(Species.objects.for_club(club).values_list("name", flat=True))
    assert names == ["Zebra", "Alpha", "Beta"]


@pytest.mark.django_db
def test_verbose_name_plural_species(club):
    """Species verbose_name_plural is 'Species'."""
    from django.apps import apps

    model = apps.get_model("character_options", "Species")
    assert model._meta.verbose_name_plural == "Species"
