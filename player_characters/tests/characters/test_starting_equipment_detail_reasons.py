"""Surface: the character detail page lists the missing-gear reasons."""

import pytest
from django.urls import reverse

from character_options.models import Background, CharacterClass
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentClassEntry,
    StartingEquipmentTemplate,
)

pytestmark = [pytest.mark.django_db]


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


@pytest.fixture
def fighter_class(club):
    return CharacterClass.objects.create(club=club, name="Fighter", is_active=True, sort_order=10)


@pytest.fixture
def acolyte_bg(club):
    return Background.objects.create(club=club, name="Acolyte", is_active=True, sort_order=10)


@pytest.fixture
def active_template(club, fighter_class, acolyte_bg):
    """Non-empty template: Fighter class entry + Acolyte background entry."""
    template = StartingEquipmentTemplate.objects.create(
        club=club, name="Active Template", is_active=True
    )
    StartingEquipmentClassEntry.objects.create(
        template=template,
        class_option=fighter_class,
        min_level=1,
        max_level=20,
        coins_cp=1000,
    )
    StartingEquipmentBackgroundEntry.objects.create(
        template=template,
        background_option=acolyte_bg,
        coins_cp=500,
    )
    return template


def _get(client, club, character):
    response = client.get(detail_url(club, character))
    assert response.status_code == 200
    return response


class TestDetailReasonsSection:
    def test_reasons_shown_when_gear_missing(self, club, login, player, character, active_template):
        """A character with custom class/background shows the reasons section."""
        character.char_class = "Artificer"
        character.class_option = None
        character.background = "Homebrew Background"
        character.background_option = None
        character.level = 1
        character.starting_equipment_claimed = False
        character.save()

        client = login(player)
        response = _get(client, club, character)

        content = response.content.decode()
        assert "Artificer" in content
        assert "Homebrew Background" in content
        assert "custom value" in content

    def test_no_reasons_section_when_all_matched(
        self, club, login, player, character, active_template, fighter_class, acolyte_bg
    ):
        """A fully matched character has no reasons section."""
        character.char_class = "Fighter"
        character.class_option = fighter_class
        character.background = "Acolyte"
        character.background_option = acolyte_bg
        character.level = 1
        character.starting_equipment_claimed = False
        character.save()

        client = login(player)
        response = _get(client, club, character)

        content = response.content.decode()
        assert "custom value" not in content
        assert "Starting equipment notes" not in content

    def test_no_reasons_section_when_no_template(self, club, login, player, character):
        """No template -> no reasons section (no_template is skipped on the detail page)."""
        character.char_class = "Fighter"
        character.background = ""
        character.level = 1
        character.starting_equipment_claimed = False
        character.save()

        client = login(player)
        response = _get(client, club, character)

        content = response.content.decode()
        assert "Starting equipment notes" not in content

    def test_partial_grant_still_explained(
        self, club, login, player, character, active_template, fighter_class
    ):
        """A granted entry can still carry reasons (custom background)."""
        character.char_class = "Fighter"
        character.class_option = fighter_class
        character.background = "Homebrew Background"
        character.background_option = None
        character.level = 1
        character.starting_equipment_claimed = False
        character.save()

        client = login(player)
        response = _get(client, club, character)

        content = response.content.decode()
        assert "Homebrew Background" in content
        assert "custom value" in content
