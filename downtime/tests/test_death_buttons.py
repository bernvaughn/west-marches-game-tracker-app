"""Tests for U140: downtime spend buttons replaced by death reason."""

import pytest
from django.test import Client
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


def _get_page(client, url):
    return client.get(url).content.decode()


def result_modal_body(client, url):
    resp = client.get(url, **{"HTTP_HX_REQUEST": "true"})
    return resp.content.decode()


@pytest.fixture
def logged_in_client(player):
    """A test client with the player logged in."""
    client = Client()
    client.force_login(player)
    return client


def test_play_page_dead_shows_reason(club, logged_in_client, character, action, entries):
    """Play page shows reason instead of 'Take the job' when character is dead."""

    services.award(character, 2)
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    _select_character(logged_in_client, character)

    url = reverse("downtime:play", args=[club.slug])
    body = _get_page(logged_in_client, url)

    assert "Aria died on" in body
    assert "Take the job" not in body


def test_play_page_archived_shows_reason(club, logged_in_client, character, action, entries):
    """Play page shows reason when character is archived."""

    services.award(character, 2)
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])
    _select_character(logged_in_client, character)

    url = reverse("downtime:play", args=[club.slug])
    body = _get_page(logged_in_client, url)

    assert "Aria is archived" in body
    assert "Take the job" not in body


def test_play_page_living_shows_take_job(club, logged_in_client, character, action, entries):
    """Play page shows 'Take the job' for living character with points."""

    services.award(character, 2)
    _select_character(logged_in_client, character)

    url = reverse("downtime:play", args=[club.slug])
    body = _get_page(logged_in_client, url)

    assert "Take the job" in body
    assert "died on" not in body
    assert "is archived" not in body


def test_result_modal_dead_shows_reason_instead_of_spin_again(
    club, logged_in_client, player, character, action, entries
):
    """Result modal shows reason instead of 'Spin again' when character is dead."""

    services.award(character, 2)
    _select_character(logged_in_client, character)
    result = services.spend(character, action, player)

    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])

    url = reverse("downtime:result", args=[club.slug, result.pk])
    body = result_modal_body(logged_in_client, url)

    assert "Aria died on" in body
    assert "Spin again" not in body


def test_result_modal_archived_shows_reason_instead_of_spin_again(
    club, logged_in_client, player, character, action, entries
):
    """Result modal shows reason instead of 'Spin again' when character is archived."""

    services.award(character, 2)
    _select_character(logged_in_client, character)
    result = services.spend(character, action, player)

    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])

    url = reverse("downtime:result", args=[club.slug, result.pk])
    body = result_modal_body(logged_in_client, url)

    assert "Aria is archived" in body
    assert "Spin again" not in body


def test_result_modal_living_shows_spin_again(
    club, logged_in_client, player, character, action, entries
):
    """Result modal shows 'Spin again' for living character."""

    services.award(character, 2)
    _select_character(logged_in_client, character)
    result = services.spend(character, action, player)

    url = reverse("downtime:result", args=[club.slug, result.pk])
    body = result_modal_body(logged_in_client, url)

    assert "Spin again" in body
    assert "died on" not in body
    assert "is archived" not in body
