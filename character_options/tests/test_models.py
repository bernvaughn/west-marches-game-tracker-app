"""Tests for character option models."""

import pytest
from django.db import IntegrityError, transaction

from accounts.models import Club
from character_options.models import Background, CharacterClass, Species


@pytest.mark.django_db
def test_unique_per_club_case_insensitive(unseeded_club):
    """Creating 'fighter' when 'Fighter' exists raises IntegrityError."""
    CharacterClass.objects.create(club=unseeded_club, name="Fighter")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CharacterClass.objects.create(club=unseeded_club, name="fighter")


@pytest.mark.django_db
def test_same_name_allowed_in_another_club(unseeded_club):
    """Same name is allowed in a different club."""
    # Create an unseeded other club
    other_club = Club.objects.create(name="Club B", slug="club-b")
    # Use a name not in the defaults to avoid fixture conflict
    CharacterClass.objects.create(club=unseeded_club, name="CustomFighter")
    CharacterClass.objects.create(club=other_club, name="CustomFighter")

    assert CharacterClass.objects.for_club(unseeded_club).count() == 1
    assert CharacterClass.objects.for_club(other_club).count() == 1


@pytest.mark.django_db
def test_same_name_allowed_across_kinds(unseeded_club):
    """Same name is allowed across Species, CharacterClass, Background."""
    Species.objects.create(club=unseeded_club, name="CustomFighter")
    CharacterClass.objects.create(club=unseeded_club, name="CustomFighter")
    Background.objects.create(club=unseeded_club, name="CustomFighter")

    assert Species.objects.for_club(unseeded_club).count() == 1
    assert CharacterClass.objects.for_club(unseeded_club).count() == 1
    assert Background.objects.for_club(unseeded_club).count() == 1


@pytest.mark.django_db
def test_defaults_ordering_by_sort_order(unseeded_club):
    """Records order by sort_order then name."""
    Species.objects.create(club=unseeded_club, name="Zebra", sort_order=0)
    Species.objects.create(club=unseeded_club, name="Alpha", sort_order=10)
    Species.objects.create(club=unseeded_club, name="Beta", sort_order=10)

    names = list(Species.objects.for_club(unseeded_club).values_list("name", flat=True))
    assert names == ["Zebra", "Alpha", "Beta"]


@pytest.mark.django_db
def test_verbose_name_plural_species(club):
    """Species verbose_name_plural is 'Species'."""
    from django.apps import apps

    model = apps.get_model("character_options", "Species")
    assert model._meta.verbose_name_plural == "Species"
