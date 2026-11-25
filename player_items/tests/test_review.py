"""Tests for the player-item review page (U160).

Covers grouping (case/spacing insensitive), totals and holder counts, the
"leave as is" action, the Club Admin menu count, and club-admin-only access.
"""

import pytest
from django.urls import reverse

from player_characters.models import Character
from player_items.models import PlayerItem

pytestmark = [pytest.mark.story("U160"), pytest.mark.django_db]


# --- helpers -------------------------------------------------------------


def review_url(club):
    return reverse("player_items:review", args=[club.slug])


def leave_as_is_url(club):
    return reverse("player_items:leave_as_is", args=[club.slug])


def make_item(club, character, name="Sword", quantity=1, review="open"):
    return PlayerItem.objects.create(
        club=club, character=character, name=name, quantity=quantity, review=review
    )


@pytest.fixture
def other_character(club, other_player):
    owner = club.memberships.get(user=other_player)
    return Character.objects.create(club=club, owner=owner, name="Borin")


# --- permissions ---------------------------------------------------------


def test_club_admin_can_review(club, login, club_admin):
    c = login(club_admin)
    assert c.get(review_url(club)).status_code == 200


def test_player_cannot_review(club, login, player, character):
    c = login(player)
    assert c.get(review_url(club)).status_code == 403


def test_game_master_cannot_review(club, login, game_master):
    c = login(game_master)
    assert c.get(review_url(club)).status_code == 403


def test_other_player_cannot_review(club, login, other_player):
    c = login(other_player)
    assert c.get(review_url(club)).status_code == 403


# --- grouping: case and spacing insensitive ------------------------------


def test_grouping_ignores_case_and_spacing(club, login, club_admin, character, other_character):
    """Names that differ only by case/spacing share one name_key group."""
    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion ", 3)
    make_item(club, other_character, "POTION", 1)
    make_item(club, character, "Rope", 1)

    c = login(club_admin)
    body = c.get(review_url(club)).content.decode()

    # One group for the three potion entries: total 6, two holders.
    assert "Potion" in body
    assert "6" in body
    assert "Rope" in body
    # Only two groups shown (potion + rope).
    assert body.count("Leave as is") == 2


def test_holder_count_per_group(club, login, club_admin, character, other_character):
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Potion", 3)
    make_item(club, character, "Potion", 1)

    c = login(club_admin)
    body = c.get(review_url(club)).content.decode()

    assert "Potion" in body
    assert "6" in body
    assert "2" in body  # two holders (character + other_character)


# --- leave as is ---------------------------------------------------------


def test_leave_as_is_hides_group(club, login, club_admin, character):
    make_item(club, character, "Potion", 2)
    make_item(club, character, "Rope", 1)

    c = login(club_admin)
    group = PlayerItem.objects.for_club(club).filter(name_key="potion").first()
    assert group is not None

    r = c.post(leave_as_is_url(club), {"name_key": "potion"})
    assert r.status_code == 302
    assert r["Location"] == review_url(club)

    # Item is now left_as_is, not deleted or renamed.
    item = PlayerItem.objects.for_club(club).get(name="Potion")
    assert item.review == "left_as_is"
    assert item.name == "Potion"

    # Group no longer appears on the review page.
    body = c.get(review_url(club)).content.decode()
    assert "Potion" not in body
    assert "Rope" in body


# --- menu count ----------------------------------------------------------


def test_admin_menu_shows_open_group_count(club, login, club_admin, character, other_character):
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Rope", 1)

    c = login(club_admin)
    body = c.get(review_url(club)).content.decode()

    # Two open groups -> label shows count of 2.
    assert "Review player items (2)" in body
