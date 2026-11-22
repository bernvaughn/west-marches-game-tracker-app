"""Tests for U140: quest turn-in buttons replaced by death reason."""

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.story("U140")]


def _select_character(client, character):
    """Set the selected character in session."""
    url = reverse("characters:select", args=[character.club.slug])
    client.post(url, {"character": character.pk})


@pytest.fixture
def logged_in_client(player):
    """A test client with the player logged in."""
    client = Client()
    client.force_login(player)
    return client


def _url(name, club, *args):
    return reverse(f"quests:{name}", args=[club.slug, *args])


def _body(client, club, quest):
    return client.get(_url("detail", club, quest.pk)).content.decode()


def test_turn_in_dead_shows_reason(
    club, logged_in_client, quest, character, item, give
):
    """Turn-in card shows reason instead of form when character is dead."""
    give(character, item, 2)
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    _select_character(logged_in_client, character)

    body = _body(logged_in_client, club, quest)

    assert "Aria died on" in body
    assert "Turn in as Aria" not in body
    assert "<form" not in body.split('id="turn-in"')[1]


def test_turn_in_archived_shows_reason(
    club, logged_in_client, quest, character, item, give
):
    """Turn-in card shows reason when character is archived."""
    give(character, item, 2)
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])
    _select_character(logged_in_client, character)

    body = _body(logged_in_client, club, quest)

    assert "Aria is archived" in body
    assert "Turn in as Aria" not in body
    assert "<form" not in body.split('id="turn-in"')[1]


def test_turn_in_living_shows_button(
    club, logged_in_client, quest, character, item, give
):
    """Turn-in card shows Turn in button for living character with requirements met."""
    give(character, item, 2)
    _select_character(logged_in_client, character)

    body = _body(logged_in_client, club, quest)

    assert "Turn in as Aria" in body
    assert "died on" not in body
    assert "is archived" not in body


def test_turn_in_dead_no_character_selected_shows_empty_state(
    club, player, logged_in_client, quest
):
    """When no character selected, shows empty state not death reason."""
    body = _body(logged_in_client, club, quest)

    # No character = empty state
    assert "You have no character in this club" in body
    assert "Turn in as" not in body