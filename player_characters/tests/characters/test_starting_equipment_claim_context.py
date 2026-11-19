"""Tests for the can_claim_starting_equipment context value on the character detail view."""

import pytest
from django.urls import reverse

from starting_equipment.models import StartingEquipmentTemplate

pytestmark = [pytest.mark.django_db]


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


@pytest.fixture
def active_template(club):
    return StartingEquipmentTemplate.objects.create(
        club=club, name="Active Template", is_active=True
    )


def _claim_context(client, club, character):
    """Return the can_claim_starting_equipment value from the detail view context."""
    response = client.get(detail_url(club, character))
    assert response.status_code == 200
    return response.context["can_claim_starting_equipment"]


class TestCanClaimStartingEquipmentContext:
    @pytest.mark.parametrize(
        "user_fixture,expected",
        [
            ("player", True),  # character owner
            ("club_admin", True),  # club admin
            ("game_master", True),  # game master
            ("site_admin", True),  # superuser counts as admin and GM
            ("other_player", False),  # plain club member, not the owner
        ],
    )
    def test_permission_gates_claim(
        self, request, club, login, user_fixture, expected, character, active_template
    ):
        """Only the owner, a club admin or a GM can claim starting equipment."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        user = request.getfixturevalue(user_fixture)
        client = login(user)
        assert _claim_context(client, club, character) is expected

    @pytest.mark.parametrize(
        "claimed,expected",
        [
            (False, True),
            (True, False),
        ],
    )
    def test_claimed_flag(self, club, login, player, claimed, expected, character, active_template):
        """An unclaimed character can claim; a claimed character cannot."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = claimed
        character.save()
        client = login(player)
        assert _claim_context(client, club, character) is expected

    @pytest.mark.parametrize(
        "template_fixture,expected",
        [
            ("active_template", True),
            (None, False),
        ],
    )
    def test_active_template_required(
        self, request, club, login, player, template_fixture, expected, character
    ):
        """Claiming requires an active template for the club."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        if template_fixture is not None:
            request.getfixturevalue(template_fixture)
        client = login(player)
        assert _claim_context(client, club, character) is expected

    @pytest.mark.parametrize(
        "char_class,background,expected",
        [
            ("Fighter", "", True),  # class only
            ("", "Acolyte", True),  # background only
            ("Fighter", "Acolyte", True),  # both class and background
            ("", "", False),  # neither class nor background
        ],
    )
    def test_class_or_background_required(
        self, club, login, player, char_class, background, expected, character, active_template
    ):
        """The character needs a class or a background to claim starting equipment."""
        character.char_class = char_class
        character.background = background
        character.starting_equipment_claimed = False
        character.save()
        client = login(player)
        assert _claim_context(client, club, character) is expected

    def test_all_conditions_block_claim(self, club, login, player, character):
        """With every condition unmet, the context value is False."""
        character.char_class = ""
        character.background = ""
        character.starting_equipment_claimed = True
        character.save()
        client = login(player)
        assert _claim_context(client, club, character) is False

    def test_context_key_always_present(self, club, login, player, character, active_template):
        """The context always exposes the key, even when the value is False."""
        character.char_class = "Fighter"
        character.starting_equipment_claimed = False
        character.save()
        client = login(player)
        response = client.get(detail_url(club, character))
        assert response.status_code == 200
        assert "can_claim_starting_equipment" in response.context
