"""Tests for the fallen characters page (U147)."""

import pytest
from django.urls import reverse
from django.utils import dateformat, timezone

pytestmark = pytest.mark.story("U147")


def fallen_url(club):
    return reverse("characters:fallen", args=[club.slug])


def _membership(user, club):
    from accounts.models import Membership

    return Membership.objects.get(user=user, club=club)


# --- Access ---


@pytest.mark.story("U147")
def test_anonymous_redirects(client, club):
    resp = client.get(fallen_url(club))
    assert resp.status_code == 302


@pytest.mark.story("U147")
def test_non_member_404(client, club, login):
    """Non-members of the club get 404 (middleware behavior)."""
    from accounts.models import User

    user = User.objects.create_user("nomember@example.com", password="pw", display_name="No Member")
    resp = login(user).get(fallen_url(club))
    assert resp.status_code == 404


# --- Visibility: every club member sees all dead characters ---


@pytest.mark.story("U147")
def test_player_sees_all_dead_characters(
    login, club, player, other_player, character, other_character
):
    """Every club member sees all dead characters, not just their own."""
    character.died_on = timezone.localdate()
    character.save()
    other_character.died_on = timezone.localdate()
    other_character.save()

    body = login(player).get(fallen_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert f">{other_character.name}<" in body


@pytest.mark.story("U147")
def test_archived_dead_character_included(login, club, player, character):
    """Archived dead characters are included on the Fallen page."""
    character.died_on = timezone.localdate()
    character.archived_at = timezone.now()
    character.save()

    body = login(player).get(fallen_url(club)).content.decode()
    assert f">{character.name}<" in body


@pytest.mark.story("U147")
def test_living_character_not_listed(login, club, player, character):
    """A living character is not listed."""
    body = login(player).get(fallen_url(club)).content.decode()
    assert f">{character.name}<" not in body


# --- GM / club admin / site admin see all ---


@pytest.mark.story("U147")
def test_gm_sees_all_with_owners(
    login, club, game_master, player, other_player, character, other_character
):
    """GM sees all dead characters with owner names."""
    character.died_on = timezone.localdate()
    character.save()
    other_character.died_on = timezone.localdate()
    other_character.save()

    body = login(game_master).get(fallen_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert f">{other_character.name}<" in body
    assert character.owner.user.display_name in body
    assert other_character.owner.user.display_name in body


@pytest.mark.story("U147")
def test_site_admin_sees_all(login, club, site_admin, player, character):
    """Site admin sees all dead characters."""
    character.died_on = timezone.localdate()
    character.save()

    body = login(site_admin).get(fallen_url(club)).content.decode()
    assert f">{character.name}<" in body


# --- Cross-club isolation ---


@pytest.mark.story("U147")
def test_other_club_characters_not_shown(
    login, club, game_master, player, character, foreign_character
):
    """Characters from another club never appear."""
    character.died_on = timezone.localdate()
    character.save()
    foreign_character.died_on = timezone.localdate()
    foreign_character.save()

    body = login(game_master).get(fallen_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert f">{foreign_character.name}<" not in body


# --- Ordering ---


@pytest.mark.story("U147")
def test_ordering_newest_first(login, club, player, character, other_character):
    """Dead characters are ordered by died_on newest first, then by name."""
    from datetime import timedelta

    yesterday = timezone.localdate() - timedelta(days=1)
    today = timezone.localdate()

    character.died_on = yesterday
    character.name = "Aria"
    character.save()
    other_character.died_on = today
    other_character.name = "Borin"
    other_character.save()

    body = login(player).get(fallen_url(club)).content.decode()
    first = body.index(f">{other_character.name}<")
    second = body.index(f">{character.name}<")
    assert first < second


# --- Row content ---


@pytest.mark.story("U147")
def test_row_shows_name_class_level_died_note_owner(login, club, player, character):
    """Row shows name, class, level, death date, note, and owner."""
    character.char_class = "Fighter"
    character.level = 3
    character.died_on = timezone.localdate()
    character.death_note = "Slain by a dragon."
    character.save()

    body = login(player).get(fallen_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert "Fighter" in body
    assert "Level 3" in body
    assert dateformat.format(character.died_on, "d M Y") in body
    assert "Slain by a dragon." in body
    assert character.owner.user.display_name in body


# --- Empty state ---


@pytest.mark.story("U147")
def test_empty_state(login, club, player):
    """No dead characters shows the empty state."""
    body = login(player).get(fallen_url(club)).content.decode()
    assert "No fallen characters." in body


# --- Nav: side menu links to fallen ---


@pytest.mark.story("U147")
def test_nav_links_fallen(login, club, player):
    """The side menu for a player links characters:fallen."""
    body = login(player).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    url = reverse("characters:fallen", args=[club.slug])
    assert f'href="{url}"' in body
