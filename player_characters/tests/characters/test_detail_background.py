"""Tests for background display on the character detail sheet."""

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db]


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


class TestDetailBackgroundDisplay:
    def test_renders_background_in_header_when_set(self, club, login, player, character):
        """Detail view renders background in header when character has background set."""
        character.background = "Acolyte"
        character.char_class = "Cleric"
        character.species = "Human"
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
        character.background = "Soldier"
        character.char_class = "Fighter"
        character.species = "Elf"
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
        character.background = "Hermit"
        character.char_class = "Wizard"
        character.species = ""
        character.pronouns = ""
        character.alignment = ""
        character.save()

        client = login(player)
        response = client.get(detail_url(club, character))
        assert response.status_code == 200

        content = response.content.decode()
        # Should show: Level · Class · Background (no species, pronouns, alignment)
        assert "Wizard &middot; Hermit" in content
