"""Tests for background display on the character detail sheet."""

import pytest
from django.urls import reverse

from character_options.models import Background, CharacterClass, Species

pytestmark = [pytest.mark.django_db]


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def link(character, **values):
    """Set the text fields and link each to a club record, so no "custom" badge shows."""
    models = {"char_class": CharacterClass, "species": Species, "background": Background}
    fks = {"char_class": "class_option", "species": "species_option"}
    for field, name in values.items():
        setattr(character, field, name)
        record = models[field].objects.create(club=character.club, name=name) if name else None
        setattr(character, fks.get(field, "background_option"), record)


class TestDetailBackgroundDisplay:
    def test_renders_background_in_header_when_set(self, club, login, player, character):
        """Detail view renders background in header when character has background set."""
        link(character, background="Acolyte", char_class="Cleric", species="Human")
        character.save()

        client = login(player)
        response = client.get(detail_url(club, character))
        assert response.status_code == 200

        content = response.content.decode()
        # Background should appear in the header line
        assert "Acolyte" in content
        # Check it's in the header paragraph (after species, before pronouns)
        assert "Human &middot; Acolyte" in content

    def test_does_not_render_background_in_header_when_empty(self, club, login, player, character):
        """Detail view does not render background in header when character has no background."""
        character.background = ""
        character.char_class = "Fighter"
        character.species = "Dwarf"
        character.save()

        client = login(player)
        response = client.get(detail_url(club, character))
        assert response.status_code == 200

        content = response.content.decode()
        # Background should not appear in the header line
        assert "Acolyte" not in content
        # Header should not have extra middot for empty background
        assert "Dwarf &middot; &middot;" not in content

    def test_background_position(self, club, login, player, character):
        """Background appears in correct position: after species, before pronouns."""
        link(character, background="Soldier", char_class="Fighter", species="Elf")
        character.pronouns = "they/them"
        character.alignment = "Lawful good"
        character.save()

        client = login(player)
        response = client.get(detail_url(club, character))
        assert response.status_code == 200

        content = response.content.decode()
        # Verify the order: Level · Class · Species · Background · Pronouns · Alignment
        assert "Elf &middot; Soldier &middot; they/them &middot; Lawful good" in content

    def test_background_with_only_some_fields(self, club, login, player, character):
        """Background renders correctly when only some header fields are set."""
        link(character, background="Hermit", char_class="Wizard", species="")
        character.pronouns = ""
        character.alignment = ""
        character.save()

        client = login(player)
        response = client.get(detail_url(club, character))
        assert response.status_code == 200

        content = response.content.decode()
        # Should show: Level · Class · Background (no species, pronouns, alignment)
        assert "Wizard &middot; Hermit" in content


def test_custom_values_show_a_badge_in_the_header(club, login, player, character):
    """Text with no linked record is custom and gets a badge."""
    character.background = "Hedge Knight"
    character.save()
    content = login(player).get(detail_url(club, character)).content.decode()
    assert "Hedge Knight" in content
    assert 'wm-badge--warning">custom</span>' in content
