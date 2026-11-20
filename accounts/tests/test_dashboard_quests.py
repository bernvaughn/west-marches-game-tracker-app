"""Tests for dashboard quest turn-in HTMX endpoint."""

import pathlib

import pytest
from django.urls import reverse
from django.utils import timezone

from quests.models import QuestCompletion

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _url(name, *args):
    return reverse(f"accounts:{name}", args=["club-a", *args])


def _body(client, url):
    return client.get(url).content.decode()


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_get_renders_modal(login, player, quest, character, item, give):
    """GET request returns the turn-in modal fragment."""
    give(character, item, 2)  # enough for requirements
    c = login(player)
    url = _url("dashboard_quest_turnin", quest.pk)
    response = c.get(url)
    assert response.status_code == 200
    body = response.content.decode()
    assert 'id="turn-in"' in body
    assert character.name in body
    assert "OK" in body  # items are available
    assert "Turn in as" in body


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_get_shows_missing_when_not_enough(
    login, player, quest, character, item
):
    """GET request shows missing items when character doesn't have enough."""
    c = login(player)
    url = _url("dashboard_quest_turnin", quest.pk)
    response = c.get(url)
    assert response.status_code == 200
    body = response.content.decode()
    assert "Missing" in body
    assert "disabled" in body.split('id="turn-in"')[1]


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_post_success(login, player, quest, character, item, give):
    """POST request with sufficient items completes the quest."""
    give(character, item, 2)
    c = login(player)
    url = _url("dashboard_quest_turnin", quest.pk)
    response = c.post(url)
    assert response.status_code == 204
    assert response["HX-Trigger"] is not None
    trigger = response["HX-Trigger"]
    assert "appModalClose" in trigger
    assert "toast" in trigger
    assert "dashboardRefresh" in trigger
    # Quest completion was created
    assert QuestCompletion.objects.filter(quest=quest, character=character).count() == 1


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_post_insufficient_items(login, player, quest, character, item):
    """POST request with insufficient items returns 400 with error modal."""
    c = login(player)
    url = _url("dashboard_quest_turnin", quest.pk)
    response = c.post(url)
    assert response.status_code == 400
    body = response.content.decode()
    assert "Missing" in body
    assert "disabled" in body


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_post_quest_not_live(login, player, quest, character, item, give):
    """POST request when quest is not live returns 404."""
    give(character, item, 2)
    quest.end_date = timezone.localdate() - timezone.timedelta(days=1)
    quest.save()
    c = login(player)
    url = _url("dashboard_quest_turnin", quest.pk)
    response = c.post(url)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_post_club_full(
    login, player, quest, character, item, give, other_player, club
):
    """POST request when quest is full returns error."""
    from accounts.models import Membership
    from player_characters.models import Character

    owner = Membership.objects.get(user=other_player, club=club)
    other = Character.objects.create(club=club, owner=owner, name="Other")
    give(character, item, 2)
    quest.max_completions = 1
    quest.save()
    QuestCompletion.objects.create(quest=quest, character=other, date=timezone.localdate())
    c = login(player)
    url = _url("dashboard_quest_turnin", quest.pk)
    response = c.post(url)
    assert response.status_code == 400
    body = response.content.decode()
    assert "This quest is full" in body


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_post_per_character_limit(
    login, player, quest, character, item, give
):
    """POST request when character hit per-character limit returns error."""
    give(character, item, 4)
    quest.max_per_character = 1
    quest.save()
    c = login(player)
    # First turn-in succeeds
    c.post(_url("dashboard_quest_turnin", quest.pk))
    # Second turn-in fails
    url = _url("dashboard_quest_turnin", quest.pk)
    response = c.post(url)
    assert response.status_code == 400
    body = response.content.decode()
    assert "maximum number of times" in body


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_no_character(login, other_player, club, quest):
    """Returns 404 when user has no character in club."""
    from accounts.models import Membership, User

    user = User.objects.create_user("nochar@example.com", password="x", display_name="N")
    Membership.objects.create(user=user, club=club)
    c = login(user)
    url = _url("dashboard_quest_turnin", quest.pk)
    response = c.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_cross_club_404(login, player, other_club_quest):
    """Returns 404 for quest in another club."""
    c = login(player)
    url = _url("dashboard_quest_turnin", other_club_quest.pk)
    response = c.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.story("S4")
def test_dashboard_quest_turnin_not_live_404(login, player, upcoming_quest, character, item, give):
    """Returns 404 for quest not yet live."""
    give(character, item, 2)
    c = login(player)
    url = _url("dashboard_quest_turnin", upcoming_quest.pk)
    response = c.get(url)
    assert response.status_code == 404


def test_dashboard_quest_buttons_above_stretched_link():
    """Buttons in quest rows sit above the stretched-link overlay (z-index fix).

    The stretched-link::after pseudo-element covers the list-group-item at z-index 1.
    Buttons need position: relative and z-index: 2 to be clickable.
    """
    css = (ROOT / "static/css/areas/accounts.css").read_text()
    # Check for the rule that raises buttons above the stretched link overlay
    assert ".wm-dashboard-section .list-group-item .btn {" in css
    assert "position: relative" in css
    assert "z-index: 2" in css
