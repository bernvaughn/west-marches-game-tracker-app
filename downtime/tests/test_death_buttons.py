"""Tests for U140: downtime spend buttons replaced by death reason."""

from urllib.parse import urlencode

import pytest
from django.urls import reverse
from django.utils import timezone

from downtime import services

pytestmark = [pytest.mark.django_db, pytest.mark.story("U140")]


def _today():
    return timezone.localdate()


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


def play(login, user, club, **params):
    url = reverse("downtime:play", args=[club.slug])
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    return login(user).get(url).content.decode()


def result_modal_body(login, user, club, result):
    url = reverse("downtime:result", args=[club.slug, result.pk])
    client = login(user)
    resp = client.get(url, **{"HTTP_HX_REQUEST": "true"})
    return resp.content.decode()


def test_play_page_dead_shows_reason(club, login, player, character, action, entries):
    """Play page shows reason instead of 'Take the job' when character is dead."""
    services.award(character, 2)
    _make_dead(character)
    _select_character(login(player), character)

    body = play(login, player, club)

    assert "Aria died on" in body
    assert "Take the job" not in body


def test_play_page_archived_shows_reason(club, login, player, character, action, entries):
    """Play page shows reason when character is archived."""
    services.award(character, 2)
    _make_archived(character)
    _select_character(login(player), character)

    body = play(login, player, club)

    assert "Aria is archived" in body
    assert "Take the job" not in body


def test_play_page_living_shows_take_job(club, login, player, character, action, entries):
    """Play page shows 'Take the job' for living character with points."""
    services.award(character, 2)
    _select_character(login(player), character)

    body = play(login, player, club)

    assert "Take the job" in body
    assert "died on" not in body
    assert "is archived" not in body


def test_result_modal_dead_shows_reason_instead_of_spin_again(
    club, login, player, character, action, entries
):
    """Result modal shows reason instead of 'Spin again' when character is dead."""
    services.award(character, 2)
    c = login(player)
    _select_character(c, character)
    result = services.spend(character, action, player)

    _make_dead(character)

    body = result_modal_body(login, player, club, result)

    assert "Aria died on" in body
    assert "Spin again" not in body


def test_result_modal_archived_shows_reason_instead_of_spin_again(
    club, login, player, character, action, entries
):
    """Result modal shows reason instead of 'Spin again' when character is archived."""
    services.award(character, 2)
    c = login(player)
    _select_character(c, character)
    result = services.spend(character, action, player)

    _make_archived(character)

    body = result_modal_body(login, player, club, result)

    assert "Aria is archived" in body
    assert "Spin again" not in body


def test_result_modal_living_shows_spin_again(club, login, player, character, action, entries):
    """Result modal shows 'Spin again' for living character."""
    services.award(character, 2)
    c = login(player)
    _select_character(c, character)
    result = services.spend(character, action, player)

    body = result_modal_body(login, player, club, result)

    assert "Spin again" in body
    assert "died on" not in body
    assert "is archived" not in body
