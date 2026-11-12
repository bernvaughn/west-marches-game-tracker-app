import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from map.models import Location, Tile
from map.render import build_cells
from map.services import add_found_marks, add_to_credit, record_visits
from player_characters.models import Character


def url(name, club, *args):
    return reverse(f"map:{name}", args=[club.slug, *args])


def get(client, name, club, *args, query=""):
    resp = client.get(url(name, club, *args) + query)
    return resp


@pytest.fixture
def second_location(hex_map):
    tile = Tile.objects.create(map=hex_map, q=0, r=2)
    return Location.objects.create(
        tile=tile, name="Hidden Cave", symbol="C", gm_notes="Cave GM secret", target_band="3-4"
    )


@pytest.fixture
def foreign_character(other_club, other_club_member):
    from accounts.models import Membership

    owner = Membership.objects.get(user=other_club_member, club=other_club)
    return Character.objects.create(club=other_club, owner=owner, name="Zorg")


@pytest.fixture
def two_visits(hex_map, tile_location, second_location, player_character, second_character):
    record_visits(hex_map, 1, 0, [player_character])
    record_visits(hex_map, 0, 2, [second_character])
    add_found_marks(tile_location, [player_character])
    add_found_marks(second_location, [second_character])


@pytest.mark.story("M8")
def test_player_picks_one_character(login, club, hex_map, two_visits, player, second_character):
    html = get(
        login(player), "detail", club, hex_map.pk, query=f"?characters={second_character.pk}"
    )
    body = html.content.decode()
    assert url("tile", club, hex_map.pk, 0, 2) in body
    assert url("tile", club, hex_map.pk, 1, 0) not in body
    assert f"characters={second_character.pk}" in body  # pan and tile links carry the pick
    default = get(login(player), "detail", club, hex_map.pk).content.decode()
    assert url("tile", club, hex_map.pk, 1, 0) in default
    assert url("tile", club, hex_map.pk, 0, 2) in default


@pytest.mark.story("M8")
def test_player_foreign_character_ignored(
    login, club, hex_map, two_visits, player, other_character, second_character
):
    body = get(
        login(player), "detail", club, hex_map.pk, query=f"?characters={other_character.pk}"
    ).content.decode()
    assert url("tile", club, hex_map.pk, 1, 0) in body
    assert url("tile", club, hex_map.pk, 0, 2) in body
    assert "Cael" not in body
    assert "Aria" in body and "Borin" in body


@pytest.mark.story("M8")
def test_tile_page_respects_pick(login, club, hex_map, two_visits, player, second_character):
    resp = get(
        login(player), "tile", club, hex_map.pk, 1, 0, query=f"?characters={second_character.pk}"
    )
    assert resp.status_code == 404


@pytest.mark.story("M9")
def test_player_print(login, club, hex_map, two_visits, second_location, player, player_character):
    record_visits(hex_map, 0, 0, [player_character])
    hidden = Tile.objects.create(map=hex_map, q=3, r=0)
    Location.objects.create(tile=hidden, name="Unseen Ruin")
    resp = get(login(player), "print", club, hex_map.pk)
    body = resp.content.decode()
    assert resp.status_code == 200
    assert "Old Watchtower" in body and "Player note text" in body and "CR 1-2" in body
    assert "Secret GM note" not in body
    assert "Unseen Ruin" not in body
    assert body.count("<form") == 2  # base layout: character selector (no-print) and logout
    page = get(
        login(player), "detail", club, hex_map.pk, query="?characters=" + str(player_character.pk)
    )
    assert "print/?" in page.content.decode()
    assert f"characters={player_character.pk}" in page.context["print_url"]


@pytest.mark.story("M10")
def test_gm_full_print_shows_gm_notes(login, club, hex_map, two_visits, game_master):
    body = get(login(game_master), "print", club, hex_map.pk).content.decode()
    assert "Secret GM note" in body and "Cave GM secret" in body


@pytest.mark.story("M10")
def test_gm_players_view(login, club, hex_map, two_visits, game_master, player_character):
    q = f"?view=players&characters={player_character.pk}"
    resp = get(login(game_master), "detail", club, hex_map.pk, query=q)
    body = resp.content.decode()
    assert url("tile", club, hex_map.pk, 1, 0) in body
    assert url("tile", club, hex_map.pk, 0, 2) not in body
    assert "view=players" in resp.context["print_url"]
    assert "view=players" in resp.context["pan"][0]["url"]
    assert f"characters={player_character.pk}" in resp.context["pan"][0]["url"]
    tile = get(login(game_master), "tile", club, hex_map.pk, 1, 0, query=q).content.decode()
    assert "Secret GM note" not in tile
    assert get(login(game_master), "tile", club, hex_map.pk, 0, 2, query=q).status_code == 404
    printed = get(login(game_master), "print", club, hex_map.pk, query=q).content.decode()
    assert "Secret GM note" not in printed
    assert "Old Watchtower" in printed and "Hidden Cave" not in printed


@pytest.mark.story("M15")
def test_unexplored_marker(login, club, hex_map, tile_location, player, player_character):
    add_to_credit(tile_location, "discovered", [player_character])
    client = login(player)
    detail = get(client, "detail", club, hex_map.pk).content.decode()
    assert "hex-unexplored" in detail
    tile = get(client, "tile", club, hex_map.pk, 1, 0).content.decode()
    assert "Unexplored" in tile
    assert "Discovered by: Aria" in tile and "CR 1-2" in tile
    add_to_credit(tile_location, "explored", [player_character])
    detail = get(client, "detail", club, hex_map.pk).content.decode()
    assert "hex-unexplored" not in detail
    tile = get(client, "tile", club, hex_map.pk, 1, 0).content.decode()
    assert "Unexplored" not in tile and "Explored by: Aria" in tile


@pytest.mark.story("M15")
def test_build_cells_query_count(hex_map, tile_location):
    with CaptureQueriesContext(connection) as ctx:
        build_cells(hex_map, 0, 0, 3)
    assert len(ctx) == 2


@pytest.mark.story("M8")
def test_cross_club_404(login, club, hex_map, tile_location, other_club_member):
    client = login(other_club_member)
    assert get(client, "detail", club, hex_map.pk).status_code == 404
    assert get(client, "tile", club, hex_map.pk, 1, 0).status_code == 404
    assert get(client, "print", club, hex_map.pk).status_code == 404


@pytest.mark.story("M10")
def test_foreign_character_ignored_in_gm_view(
    login, club, hex_map, two_visits, game_master, foreign_character
):
    resp = get(
        login(game_master),
        "detail",
        club,
        hex_map.pk,
        query=f"?view=players&characters={foreign_character.pk}",
    )
    body = resp.content.decode()
    assert url("tile", club, hex_map.pk, 1, 0) not in body
    assert "Zorg" not in body
    printed = get(
        login(game_master),
        "print",
        club,
        hex_map.pk,
        query=f"?view=players&characters={foreign_character.pk}",
    ).content.decode()
    assert "Zorg" not in printed and "Old Watchtower" not in printed
