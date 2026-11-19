"""Tests for the 'Claim Starting Equipment' button in the character detail toolbar."""

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from starting_equipment.models import StartingEquipmentTemplate

pytestmark = [pytest.mark.django_db]


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def claim_url(club, character):
    return reverse(
        "starting_equipment:claim",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


@pytest.fixture
def active_template(club):
    """Active starting equipment template for the club."""
    return StartingEquipmentTemplate.objects.create(
        club=club, name="Active Template", is_active=True
    )


def _button(content, club, character):
    """Return the claim button element, or None when it is not rendered."""
    soup = BeautifulSoup(content, "html.parser")
    expected_url = claim_url(club, character)
    for button in soup.find_all("button"):
        if button.get("aria-label") == "Claim starting equipment":
            assert button.get("hx-post") == expected_url
            return button
    return None


def _get(client, club, character):
    response = client.get(detail_url(club, character))
    assert response.status_code == 200
    return response.content.decode()


class TestButtonVisibility:
    """The button shows only when the character is eligible to claim."""

    @pytest.mark.parametrize(
        "user_fixture",
        ["player", "club_admin", "game_master", "site_admin"],
    )
    def test_button_visible_when_eligible(
        self, request, club, login, user_fixture, character, active_template
    ):
        """Owner, admin, GM and site admin see the button when claimable."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        user = request.getfixturevalue(user_fixture)
        content = _get(login(user), club, character)
        assert _button(content, club, character) is not None

    def test_button_absent_when_already_claimed(
        self, club, login, player, character, active_template
    ):
        """A claimed character no longer shows the button."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = True
        character.save()
        content = _get(login(player), club, character)
        assert _button(content, club, character) is None

    def test_button_absent_when_no_active_template(self, club, login, player, character):
        """No button when the club has no active starting equipment template."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        content = _get(login(player), club, character)
        assert _button(content, club, character) is None

    def test_button_absent_when_class_and_background_missing(
        self, club, login, player, character, active_template
    ):
        """No button when the character has neither class nor background set."""
        character.char_class = ""
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        content = _get(login(player), club, character)
        assert _button(content, club, character) is None

    @pytest.mark.parametrize(
        "char_class,background",
        [
            ("Fighter", ""),  # class only
            ("", "Acolyte"),  # background only
            ("Fighter", "Acolyte"),  # both class and background
        ],
    )
    def test_button_present_when_class_or_background_set(
        self, club, login, player, char_class, background, character, active_template
    ):
        """Button shows when the character has a class or a background."""
        character.char_class = char_class
        character.background = background
        character.starting_equipment_claimed = False
        character.save()
        content = _get(login(player), club, character)
        assert _button(content, club, character) is not None

    def test_button_absent_for_other_member(
        self, club, login, other_player, character, active_template
    ):
        """A plain club member who is not the owner sees no button."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        content = _get(login(other_player), club, character)
        assert _button(content, club, character) is None


class TestButtonHtmxAttributes:
    """The button posts to the claim view and targets the app modal."""

    def test_hx_posts_to_claim_url(self, club, login, player, character, active_template):
        """hx-post targets the starting_equipment:claim URL."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        button = _button(_get(login(player), club, character), club, character)
        assert button is not None
        assert button.get("hx-post") == claim_url(club, character)

    def test_hx_target_is_app_modal_content(self, club, login, player, character, active_template):
        """hx-target swaps into the app modal content."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        button = _button(_get(login(player), club, character), club, character)
        assert button is not None
        assert button.get("hx-target") == "#app-modal .modal-content"

    def test_hx_swap_is_inner_html(self, club, login, player, character, active_template):
        """hx-swap replaces the modal content inner HTML."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        button = _button(_get(login(player), club, character), club, character)
        assert button is not None
        assert button.get("hx-swap") == "innerHTML"

    def test_data_app_modal_present(self, club, login, player, character, active_template):
        """data-app-modal marks the button as a modal trigger."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        button = _button(_get(login(player), club, character), club, character)
        assert button is not None
        assert button.has_attr("data-app-modal")


class TestButtonTooltipAndIcon:
    """The button carries its tooltip and box icon."""

    def test_tooltip_title(self, club, login, player, character, active_template):
        """The tooltip explains the one-time claim."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        button = _button(_get(login(player), club, character), club, character)
        assert button is not None
        assert (
            button.get("title")
            == "Claim your starting equipment (class, background, level coins). One-time only."
        )

    def test_box_icon_present(self, club, login, player, character, active_template):
        """The button includes the box icon."""
        character.char_class = "Fighter"
        character.background = ""
        character.starting_equipment_claimed = False
        character.save()
        button = _button(_get(login(player), club, character), club, character)
        assert button is not None
        use = button.find("use")
        assert use is not None
        assert "#box" in use.get("href", "")
