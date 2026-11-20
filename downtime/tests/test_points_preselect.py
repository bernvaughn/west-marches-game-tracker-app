"""Tests for downtime points preselection via ?characters= and ?character= params."""

import pytest
from django.urls import reverse

from accounts.models import Membership
from player_characters.models import Character

pytestmark = [pytest.mark.story("D1"), pytest.mark.django_db]


def url(club):
    return reverse("downtime:points_award", args=[club.slug])


@pytest.fixture
def second_character(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.mark.story("D1")
def test_points_preselect_characters_comma_list(
    login, game_master, club, character, second_character
):
    """?characters=1,2 pre-ticks both characters."""
    c = login(game_master)
    r = c.get(url(club), {"characters": f"{character.pk},{second_character.pk}"})
    assert r.status_code == 200
    html = r.content.decode()
    assert f'id="award-{character.pk}"' in html
    assert f'id="award-{second_character.pk}"' in html
    assert "checked" in html.split(f'id="award-{character.pk}"')[1].split(">")[0]
    assert "checked" in html.split(f'id="award-{second_character.pk}"')[1].split(">")[0]


@pytest.mark.story("D1")
def test_points_preselect_mixed_valid_foreign_invalid(
    login, game_master, club, character, other_club_character
):
    """Mixed valid + foreign + abc + -1 + empty + unicode digit
    returns 200 and ticks only club ones."""
    c = login(game_master)
    # Mix of valid, foreign, non-digit, negative, empty, unicode superscript 2
    r = c.get(
        url(club),
        {"characters": f"{character.pk},{other_club_character.pk},abc,-1,,²"},
    )
    assert r.status_code == 200
    html = r.content.decode()
    # Only the valid club character should be checked
    assert "checked" in html.split(f'id="award-{character.pk}"')[1].split(">")[0]
    # The foreign character is outside the club, so it has no checkbox.
    assert f'id="award-{other_club_character.pk}"' not in html


@pytest.mark.story("D1")
def test_points_preselect_singular_character_still_works(login, game_master, club, character):
    """?character= still works (backward compatibility)."""
    c = login(game_master)
    r = c.get(url(club), {"character": character.pk})
    assert r.status_code == 200
    html = r.content.decode()
    assert "checked" in html.split(f'id="award-{character.pk}"')[1].split(">")[0]


@pytest.mark.story("D1")
def test_points_preselect_huge_list_capped(login, game_master, club, character):
    """A huge list is capped (200 tokens)."""
    c = login(game_master)
    # Create many character IDs (some may not exist)
    many_ids = ",".join(str(i) for i in range(1, 300))
    r = c.get(url(club), {"characters": many_ids})
    assert r.status_code == 200
    # Should not error, just cap at 200
    html = r.content.decode()
    assert "Downtime points" in html


@pytest.mark.story("D1")
def test_points_preselect_non_gm_still_403(login, player, club):
    """Non-GM still gets 403."""
    c = login(player)
    r = c.get(url(club), {"characters": "1,2,3"})
    assert r.status_code == 403


@pytest.mark.story("D1")
def test_points_preselect_both_params_merged(login, game_master, club, character, second_character):
    """Both ?character= and ?characters= are merged (deduped)."""
    c = login(game_master)
    params = {"character": character.pk, "characters": f"{character.pk},{second_character.pk}"}
    r = c.get(url(club), params)
    assert r.status_code == 200
    html = r.content.decode()
    assert "checked" in html.split(f'id="award-{character.pk}"')[1].split(">")[0]
    assert "checked" in html.split(f'id="award-{second_character.pk}"')[1].split(">")[0]


@pytest.mark.story("D1")
def test_points_preselect_empty_and_whitespace_ignored(login, game_master, club, character):
    """Empty tokens and whitespace are ignored."""
    c = login(game_master)
    r = c.get(url(club), {"characters": f" , {character.pk} , "})
    assert r.status_code == 200
    html = r.content.decode()
    assert "checked" in html.split(f'id="award-{character.pk}"')[1].split(">")[0]


@pytest.mark.story("D1")
def test_points_preselect_singular_unicode_digit_ignored(login, game_master, club, character):
    """?character=² passes str.isdigit() but is not an ASCII id. It is ignored."""
    c = login(game_master)
    r = c.get(url(club), {"character": ["²", str(character.pk)]})
    assert r.status_code == 200
    html = r.content.decode()
    assert "checked" in html.split(f'id="award-{character.pk}"')[1].split(">")[0]
