import pytest
from django.urls import reverse

from map.models import HexMap
from map.services import add_found_marks, add_to_credit, record_visits

pytestmark = pytest.mark.story("M2")


def url(name, club, *args):
    return reverse(f"map:{name}", args=[club.slug, *args])


def test_index_archived_split(login, club, hex_map, game_master, player):
    HexMap.objects.create(club=club, name="Old World", archived=True)
    gm = login(game_master).get(url("index", club)).content.decode()
    assert "The Marches" in gm and "Old World" in gm
    pl = login(player).get(url("index", club)).content.decode()
    assert "The Marches" in pl and "Old World" not in pl


def test_player_404_on_archived(login, club, player):
    m = HexMap.objects.create(club=club, name="Old", archived=True)
    assert login(player).get(url("detail", club, m.pk)).status_code == 404


def test_detail_editor_sees_all(login, club, hex_map, tile_location, game_master):
    html = login(game_master).get(url("detail", club, hex_map.pk)).content.decode()
    assert url("tile", club, hex_map.pk, 1, 0) in html
    assert "fill: red" in html


def test_detail_player_only_visited(login, club, hex_map, tile_location, player, player_character):
    record_visits(hex_map, 1, 0, [player_character])
    html = login(player).get(url("detail", club, hex_map.pk)).content.decode()
    assert url("tile", club, hex_map.pk, 1, 0) in html
    assert url("tile", club, hex_map.pk, 0, 1) not in html


def test_detail_player_not_visited(login, club, hex_map, tile_location, player, player_character):
    html = login(player).get(url("detail", club, hex_map.pk)).content.decode()
    assert url("tile", club, hex_map.pk, 1, 0) not in html
    assert url("tile", club, hex_map.pk, 0, 0) in html


def test_no_characters_note(login, club, hex_map, other_player):
    html = login(other_player).get(url("detail", club, hex_map.pk)).content.decode()
    assert "no characters" in html


def test_pan_links_negative(login, club, hex_map, game_master):
    html = login(game_master).get(url("detail", club, hex_map.pk) + "?q=-10&r=5&radius=3").content
    assert b"q=-13&amp;r=5&amp;radius=3" in html
    assert b"q=-10&amp;r=2&amp;radius=3" in html


def test_tile_empty_position(login, club, hex_map, game_master):
    resp = login(game_master).get(url("tile", club, hex_map.pk, 7, -4))
    assert resp.status_code == 200
    assert "Nothing here yet" in resp.content.decode()


def test_tile_safe_town(login, club, hex_map, player):
    html = login(player).get(url("tile", club, hex_map.pk, 0, 0)).content.decode()
    assert "Safe town" in html


def test_tile_gm_notes_editor_only(
    login, club, hex_map, tile_location, game_master, player, player_character
):
    record_visits(hex_map, 1, 0, [player_character])
    add_found_marks(tile_location, [player_character])
    gm = login(game_master).get(url("tile", club, hex_map.pk, 1, 0)).content.decode()
    assert "Secret GM note" in gm and "Player note text" in gm and "CR 1-2" in gm
    pl = login(player).get(url("tile", club, hex_map.pk, 1, 0)).content.decode()
    assert "Secret GM note" not in pl and "Player note text" in pl


def test_tile_credit_names(login, club, hex_map, tile_location, game_master, player_character):
    add_to_credit(tile_location, "discovered", [player_character])
    html = login(game_master).get(url("tile", club, hex_map.pk, 1, 0)).content.decode()
    assert "Discovered by: Aria" in html


def test_tile_unvisited_404(login, club, hex_map, tile_location, player):
    assert login(player).get(url("tile", club, hex_map.pk, 1, 0)).status_code == 404


def test_tile_negative_coords(login, club, hex_map, game_master):
    assert login(game_master).get(url("tile", club, hex_map.pk, -3, -9)).status_code == 200


def test_cross_club_isolation(login, club, hex_map, other_map, other_club_member):
    c = login(other_club_member)
    assert c.get(url("index", club)).status_code == 404
    assert c.get(url("detail", club, hex_map.pk)).status_code == 404
    assert c.get(url("tile", club, hex_map.pk, 0, 0)).status_code == 404


def test_other_club_map_via_club_url(login, club, hex_map, other_map, game_master):
    c = login(game_master)
    assert c.get(url("detail", club, other_map.pk)).status_code == 404
    assert c.get(url("tile", club, other_map.pk, 0, 0)).status_code == 404
    assert "Foreign Lands" not in c.get(url("index", club)).content.decode()
