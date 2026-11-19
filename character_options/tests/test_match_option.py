"""Tests for match_option service."""

import pytest

from character_options.models import Background, CharacterClass, Species
from character_options.services import match_option


@pytest.mark.django_db
def test_match_exact(unseeded_club):
    """Exact match works."""
    Species.objects.create(club=unseeded_club, name="Elf")
    result = match_option(unseeded_club, Species, "Elf")
    assert result is not None
    assert result.name == "Elf"


@pytest.mark.django_db
def test_match_mixed_case(unseeded_club):
    """Case-insensitive match works."""
    Species.objects.create(club=unseeded_club, name="Elf")
    result = match_option(unseeded_club, Species, "elf")
    assert result is not None
    assert result.name == "Elf"

    result = match_option(unseeded_club, Species, "ELF")
    assert result is not None
    assert result.name == "Elf"

    result = match_option(unseeded_club, Species, "ElF")
    assert result is not None
    assert result.name == "Elf"


@pytest.mark.django_db
def test_match_surrounding_whitespace(unseeded_club):
    """Surrounding whitespace is trimmed."""
    Species.objects.create(club=unseeded_club, name="Elf")
    result = match_option(unseeded_club, Species, "  Elf  ")
    assert result is not None
    assert result.name == "Elf"


@pytest.mark.django_db
def test_match_empty_none_whitespace_returns_none(unseeded_club):
    """Empty, None, or whitespace-only returns None."""
    assert match_option(unseeded_club, Species, "") is None
    assert match_option(unseeded_club, Species, None) is None
    assert match_option(unseeded_club, Species, "   ") is None
    assert match_option(unseeded_club, Species, "\t\n") is None


@pytest.mark.django_db
def test_match_unknown_returns_none(unseeded_club):
    """Unknown name returns None."""
    result = match_option(unseeded_club, Species, "Dragonborn")
    assert result is None


@pytest.mark.django_db
def test_match_other_club_not_matched(unseeded_club, other_club):
    """Record in other club is not matched."""
    # Use a name not in the defaults to avoid fixture conflict
    Species.objects.create(club=other_club, name="CustomElf")
    result = match_option(unseeded_club, Species, "CustomElf")
    assert result is None


@pytest.mark.django_db
def test_match_archived_record_still_matches(unseeded_club):
    """Archived (inactive) record still matches."""
    species = Species.objects.create(club=unseeded_club, name="Elf", is_active=False)
    result = match_option(unseeded_club, Species, "Elf")
    assert result is not None
    assert result.pk == species.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model",
    [Species, CharacterClass, Background],
    ids=["Species", "CharacterClass", "Background"],
)
def test_match_each_model(unseeded_club, model):
    """match_option works for all three models."""
    obj = model.objects.create(club=unseeded_club, name="Test")
    result = match_option(unseeded_club, model, "Test")
    assert result is not None
    assert result.pk == obj.pk