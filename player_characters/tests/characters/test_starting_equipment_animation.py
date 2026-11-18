"""Tests for starting equipment animation flag and template rendering."""

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db]


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


class TestDetailViewAnimationFlag:
    def test_show_starting_animation_true_with_param(self, club, login, player, character):
        """Detail view context has show_starting_animation=True when
        ?starting_equipment=1 is present."""
        client = login(player)
        url = f"{detail_url(club, character)}?starting_equipment=1"
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["show_starting_animation"] is True

    def test_show_starting_animation_false_without_param(self, club, login, player, character):
        """Detail view context has show_starting_animation=False when param is absent."""
        client = login(player)
        response = client.get(detail_url(club, character))
        assert response.status_code == 200
        assert response.context["show_starting_animation"] is False

    def test_show_starting_animation_false_with_other_value(self, club, login, player, character):
        """Detail view context has show_starting_animation=False when param has other value."""
        client = login(player)
        url = f"{detail_url(club, character)}?starting_equipment=0"
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["show_starting_animation"] is False

    def test_show_starting_animation_false_with_empty_value(self, club, login, player, character):
        """Detail view context has show_starting_animation=False when param is empty."""
        client = login(player)
        url = f"{detail_url(club, character)}?starting_equipment="
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["show_starting_animation"] is False


class TestDetailTemplateAnimationRendering:
    def test_renders_animation_container_when_flag_true(self, club, login, player, character):
        """Detail template renders the animation container when show_starting_animation is true."""
        client = login(player)
        url = f"{detail_url(club, character)}?starting_equipment=1"
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="starting-coins-animation"' in content
        assert 'data-coins="' in content

    def test_does_not_render_animation_container_when_flag_false(
        self, club, login, player, character
    ):
        """Detail template does not render the animation container
        when flag is false."""
        client = login(player)
        response = client.get(detail_url(club, character))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="starting-coins-animation"' not in content

    def test_animation_container_has_correct_data_coins(self, club, login, player, character):
        """Animation container has data-coins attribute with the character's coin total."""
        client = login(player)
        url = f"{detail_url(club, character)}?starting_equipment=1"
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # The coin_summary.owned is an integer (copper)
        expected_coins = str(response.context["coins"].owned)
        assert f'data-coins="{expected_coins}"' in content
