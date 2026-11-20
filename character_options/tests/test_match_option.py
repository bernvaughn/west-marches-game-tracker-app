"""Tests for match_option service."""

import pytest

from character_options.models import Background, CharacterClass, Species
from character_options.services import match_option


@pytest.mark.django_db
def test_match_exact(club):
    """Exact match works."""
    Species.objects.create(club=club, name="Elf")
    result = match_option(club, Species, "Elf")
    assert result is not None
    assert result.name == "Elf"


@pytest.mark.django_db
def test_match_mixed_case(club):
    """Case-insensitive match works."""
    Species.objects.create(club=club, name="Elf")
    result = match_option(club, Species, "elf")
    assert result is not None
    assert result.name == "Elf"

    result = match_option(club, Species, "ELF")
    assert result is not None
    assert result.name == "Elf"

    result = match_option(club, Species, "ElF")
    assert result is not None
    assert result.name == "Elf"


@pytest.mark.django_db
def test_match_surrounding_whitespace(club):
    """Surrounding whitespace is trimmed."""
    Species.objects.create(club=club, name="Elf")
    result = match_option(club, Species, "  Elf  ")
    assert result is not None
    assert result.name == "Elf"


@pytest.mark.django_db
def test_match_empty_none_whitespace_returns_none(club):
    """Empty, None, or whitespace-only returns None."""
    assert match_option(club, Species, "") is None
    assert match_option(club, Species, None) is None
    assert match_option(club, Species, "   ") is None
    assert match_option(club, Species, "\t\n") is None


@pytest.mark.django_db
def test_match_unknown_returns_none(club):
    """Unknown name returns None."""
    result = match_option(club, Species, "Dragonborn")
    assert result is None


@pytest.mark.django_db
def test_match_other_club_not_matched(club, other_club):
    """Record in other club is not matched."""
    Species.objects.create(club=other_club, name="Elf")
    result = match_option(club, Species, "Elf")
    assert result is None


@pytest.mark.django_db
def test_match_archived_record_still_matches(club):
    """Archived (inactive) record still matches."""
    species = Species.objects.create(club=club, name="Elf", is_active=False)
    result = match_option(club, Species, "Elf")
    assert result is not None
    assert result.pk == species.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model",
    [Species, CharacterClass, Background],
    ids=["Species", "CharacterClass", "Background"],
)
def test_match_each_model(club, model):
    """match_option works for all three models."""
    obj = model.objects.create(club=club, name="Test")
    result = match_option(club, model, "Test")
    assert result is not None
    assert result.pk == obj.pk
