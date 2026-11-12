import pytest
from django.urls import reverse

from map.models import MapRequest, TileVisit
from map.services import add_found_marks, add_to_credit

pytestmark = pytest.mark.story("M18")


def _url(name, club, *args):
    return reverse(f"map:{name}", args=[club.slug, *args])


@pytest.fixture
def loc(tile_location, hex_map, character, other_character):
    add_to_credit(tile_location, "discovered", [other_character])
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    return tile_location


def _page(client, club, kind, loc, data=None):
    url = _url("request_credit", club, kind, loc.pk)
    return client.post(url, data) if data else client.get(url)


def test_found_page_secret_even_if_other_character_found(
    login, club, player, character, second_character, loc
):
    add_found_marks(loc, [second_character])
    resp = _page(login(player), club, "found", loc)
    body = resp.content.decode()
    assert "Old Watchtower" not in body
    assert "Map: The Marches. Tile: 1, 0. Location: Unknown location" in body


def test_credit_page_name_only_when_every_picked_found(
    login, club, player, character, second_character, loc
):
    add_found_marks(loc, [second_character])
    client = login(player)
    both = {"characters": [character.pk, second_character.pk], "date": "2026-01-02", "note": ""}
    resp = _page(client, club, "explored", loc, {**both, "date": "bad"})
    assert "Old Watchtower" not in resp.content.decode()
    only_found = {**both, "characters": [second_character.pk], "date": "bad"}
    resp = _page(client, club, "explored", loc, only_found)
    assert "Location: Old Watchtower" in resp.content.decode()


def test_editors_see_name(login, club, game_master, club_admin, loc):
    for user in (game_master, club_admin):
        for kind in ("found", "explored"):
            resp = _page(login(user), club, kind, loc)
            assert "Location: Old Watchtower" in resp.content.decode()


def test_queue_coordinates_and_secret(
    login, club, player, game_master, character, second_character, loc, hex_map
):
    add_found_marks(loc, [second_character])
    client = login(player)
    client.post(
        _url("request_visit", club, hex_map.pk),
        {"q": 5, "r": -3, "characters": [character.pk], "date": "2026-01-02", "note": ""},
    )
    client.post(
        _url("request_credit", club, "found", loc.pk),
        {"characters": [character.pk], "date": "2026-01-02", "note": ""},
    )
    assert MapRequest.objects.count() == 2
    body = client.get(_url("requests", club)).content.decode()
    assert "(5, -3)" in body and "(1, 0)" in body
    assert "Old Watchtower" not in body and "Unknown location" in body
    gm_body = login(game_master).get(_url("requests", club)).content.decode()
    assert "Old Watchtower" in gm_body


def test_visit_page_shows_tile(login, club, player, hex_map, character):
    resp = login(player).get(_url("request_visit", club, hex_map.pk) + "?q=2&r=4")
    assert "Tile: 2, 4" in resp.content.decode()


def test_cross_club_isolation(login, club, other_club_member, game_master, loc):
    resp = _page(login(other_club_member), club, "found", loc)
    assert resp.status_code in (403, 404)
