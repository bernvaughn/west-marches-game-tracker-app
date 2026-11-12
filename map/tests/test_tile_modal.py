import pytest

from map.models import Tile
from map.services import add_found_marks
from map.tests import test_found
from map.tests.test_found import url

placeholder_world = test_found.placeholder_world
secret = test_found.secret
undiscovered = test_found.undiscovered

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.mark.story("M17")
def test_htmx_gets_fragment(login, club, hex_map, player, placeholder_world):
    resp = login(player).get(url("tile", club, hex_map.pk, 1, 0), **HX)
    body = resp.content.decode()
    assert "modal-header" in body and "btn-close" in body
    assert "<html" not in body and "map-picker" not in body
    assert "Open full page" in body
    assert "HX-Request" in resp["Vary"]


@pytest.mark.story("M17")
def test_plain_get_is_full_page(login, club, hex_map, player, placeholder_world):
    body = login(player).get(url("tile", club, hex_map.pk, 1, 0)).content.decode()
    assert "<html" in body and "map-picker" in body and "Back to the map" in body


@pytest.mark.story("M17")
def test_player_fragment_follows_m16(
    login, club, hex_map, player, placeholder_world, undiscovered, player_character
):
    client = login(player)
    body = client.get(url("tile", club, hex_map.pk, 1, 0), **HX).content.decode()
    assert "Unknown location" in body
    for text in ["Old Watchtower", "Wyvern", "Secret GM note", "Cael"]:
        assert text not in body
    assert url("request_credit", club, "found", placeholder_world.pk) in body
    body = client.get(url("tile", club, hex_map.pk, 0, 2), **HX).content.decode()
    assert "Buried Vault" not in body and "Nothing here yet" in body
    add_found_marks(placeholder_world, [player_character])
    body = client.get(url("tile", club, hex_map.pk, 1, 0), **HX).content.decode()
    assert "Old Watchtower" in body and "Unknown location" not in body
    assert "Secret GM note" not in body


@pytest.mark.story("M17")
def test_player_unvisited_tile_404(login, club, hex_map, player, placeholder_world):
    Tile.objects.create(map=hex_map, q=5, r=5)
    assert login(player).get(url("tile", club, hex_map.pk, 5, 5), **HX).status_code == 404


@pytest.mark.story("M17")
def test_editor_fragment(login, club, hex_map, game_master, placeholder_world, player_character):
    client = login(game_master)
    body = client.get(url("tile", club, hex_map.pk, 1, 0), **HX).content.decode()
    assert "Secret GM note" in body and "Old Watchtower" in body and "/edit/" in body
    q = f"?view=players&characters={player_character.pk}"
    body = client.get(url("tile", club, hex_map.pk, 1, 0) + q, **HX).content.decode()
    assert "Unknown location" in body
    assert "Secret GM note" not in body and "Old Watchtower" not in body


@pytest.mark.story("M17")
def test_hex_links_open_modal(login, club, hex_map, player, placeholder_world, player_character):
    q = f"?characters={player_character.pk}"
    body = login(player).get(url("detail", club, hex_map.pk) + q).content.decode()
    tile_url = url("tile", club, hex_map.pk, 1, 0)
    link = next(a for a in body.split("<a ") if f'href="{tile_url}' in a)
    link = link.split(">")[0]
    assert f'hx-get="{tile_url}' in link
    assert f"characters={player_character.pk}" in link
    assert 'hx-target="#app-modal .modal-content"' in link
    assert "data-app-modal" in link and "hx-on:click" in link
    assert "hx-push-url" not in link


@pytest.mark.story("M17")
def test_print_links_stay_plain(login, club, hex_map, game_master, placeholder_world):
    resp = login(game_master).get(url("print", club, hex_map.pk))
    assert resp.status_code == 200
    assert "hx-get" not in resp.content.decode()


@pytest.mark.story("M17")
def test_cross_club_isolation(
    login, club, other_club, hex_map, other_club_member, placeholder_world
):
    client = login(other_club_member)
    assert client.get(url("tile", club, hex_map.pk, 1, 0), **HX).status_code in (403, 404)
    assert client.get(url("tile", other_club, hex_map.pk, 1, 0), **HX).status_code == 404
