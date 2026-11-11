import pytest
from django.test import RequestFactory

from accounts.models import Membership
from map.services import record_visits
from map.visibility import is_map_editor, own_characters, pick_characters, visible_positions

pytestmark = pytest.mark.story("MAP_CONTRACT")


def _req(user, club):
    req = RequestFactory().get("/")
    req.user = user
    req.club = club
    req.membership = Membership.objects.filter(user=user, club=club).first()
    return req


def test_editor_roles(club, club_admin, game_master, player, other_club_member):
    assert is_map_editor(club_admin, club)
    assert is_map_editor(game_master, club)
    assert not is_map_editor(player, club)
    assert not is_map_editor(other_club_member, club)


def test_own_characters(club, player, player_character, second_character, other_character):
    assert set(own_characters(_req(player, club))) == {player_character, second_character}


def test_own_characters_none_without_membership(club, other_club_member):
    assert not own_characters(_req(other_club_member, club)).exists()


def test_pick_filters(
    club, player, game_master, player_character, other_character, other_club, other_club_member
):
    from player_characters.models import Character

    owner = Membership.objects.get(user=other_club_member, club=other_club)
    foreign = Character.objects.create(club=other_club, owner=owner, name="Foreign")
    ids = [player_character.pk, other_character.pk, foreign.pk, "junk"]
    assert set(pick_characters(_req(player, club), ids, False)) == {player_character}
    assert set(pick_characters(_req(game_master, club), ids, True)) == {
        player_character,
        other_character,
    }


def test_visible_positions(hex_map, player_character, second_character):
    record_visits(hex_map, 2, 3, [player_character])
    assert visible_positions(hex_map, [player_character]) == {(0, 0), (2, 3)}
    assert visible_positions(hex_map, [second_character]) == {(0, 0)}
