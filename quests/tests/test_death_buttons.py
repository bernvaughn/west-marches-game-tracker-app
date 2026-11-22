"""Tests for U140: quest turn-in buttons replaced by death reason."""

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.story("U140")]


def _make_dead(character):
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])


def _make_archived(character):
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])


def _select_character(client, character):
    """Set the selected character in session."""
    url = reverse("characters:select", args=[character.club.slug])
    client.post(url, {"character": character.pk})


def _url(name, club, *args):
    return reverse(f"quests:{name}", args=[club.slug, *args])


def _body(client, club, quest):
    return client.get(_url("detail", club, quest.pk)).content.decode()


def test_turn_in_dead_shows_reason(club, login, player, quest, character, item, give):
    """Turn-in card shows reason instead of form when character is dead."""
    give(character, item, 2)
    _make_dead(character)
    _select_character(login(player), character)

    body = _body(login(player), club, quest)

    assert "Aria died on" in body
    assert "Turn in as Aria" not in body
    assert "<form" not in body.split('id="turn-in"')[1]


def test_turn_in_archived_shows_reason(club, login, player, quest, character, item, give):
    """Turn-in card shows reason when character is archived."""
    give(character, item, 2)
    _make_archived(character)
    _select_character(login(player), character)

    body = _body(login(player), club, quest)

    assert "Aria is archived" in body
    assert "Turn in as Aria" not in body
    assert "<form" not in body.split('id="turn-in"')[1]


def test_turn_in_living_shows_button(club, login, player, quest, character, item, give):
    """Turn-in card shows Turn in button for living character with requirements met."""
    give(character, item, 2)
    _select_character(login(player), character)

    body = _body(login(player), club, quest)

    assert "Turn in as Aria" in body
    assert "died on" not in body
    assert "is archived" not in body


def test_turn_in_dead_no_character_selected_shows_empty_state(club, login, player, quest):
    """When no character selected, shows empty state not death reason."""
    body = _body(login(player), club, quest)

    # No character = empty state
    assert "You have no character in this club" in body
    assert "Turn in as" not in body
