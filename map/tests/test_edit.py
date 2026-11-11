import datetime

import pytest
from django.urls import reverse

from accounts.models import Membership
from map.models import Encounter, HexMap, Location, Tile
from map.services import record_visits


def url(name, club, *args):
    return reverse(f"map:{name}", args=[club.slug, *args])


@pytest.fixture
def encounter(tile_location):
    return Encounter.objects.create(location=tile_location, description="Wolves")


@pytest.mark.story("M1")
def test_create_two_maps_with_safe_town(login, club, game_master):
    c = login(game_master)
    for name in ("One", "Two"):
        resp = c.post(url("map_create", club), {"name": name})
        assert resp.status_code == 302
    maps = HexMap.objects.filter(club=club)
    assert maps.count() == 2
    for m in maps:
        assert Tile.objects.get(map=m, q=0, r=0).is_safe_town


@pytest.mark.story("M1")
def test_club_admin_can_create(login, club, club_admin):
    assert login(club_admin).post(url("map_create", club), {"name": "X"}).status_code == 302


@pytest.mark.story("M1")
def test_player_cannot_create(login, club, player):
    c = login(player)
    assert c.get(url("map_create", club)).status_code == 403
    assert c.post(url("map_create", club), {"name": "X"}).status_code == 403
    assert not HexMap.objects.exists()


@pytest.mark.story("M1")
def test_rename_archive_unarchive(login, club, hex_map, game_master, player):
    c = login(game_master)
    c.post(url("map_edit", club, hex_map.pk), {"name": "Renamed", "archived": "on"})
    hex_map.refresh_from_db()
    assert hex_map.name == "Renamed" and hex_map.archived
    assert "Renamed" not in login(player).get(url("index", club)).content.decode()
    c.post(url("map_edit", club, hex_map.pk), {"name": "Renamed"})
    hex_map.refresh_from_db()
    assert not hex_map.archived
    assert "Renamed" in login(player).get(url("index", club)).content.decode()


@pytest.mark.story("M1")
def test_action_links_for_editor_only(login, club, hex_map, game_master, player):
    assert "New map" in login(game_master).get(url("index", club)).content.decode()
    assert "New map" not in login(player).get(url("index", club)).content.decode()
    assert (
        "Rename or archive"
        in login(game_master).get(url("detail", club, hex_map.pk)).content.decode()
    )


@pytest.mark.story("M3")
def test_two_locations_one_tile(login, club, hex_map, game_master):
    c = login(game_master)
    assert not Tile.objects.filter(map=hex_map, q=2, r=-1).exists()
    assert c.get(url("location_create", club, hex_map.pk, 2, -1)).status_code == 200
    assert not Tile.objects.filter(map=hex_map, q=2, r=-1).exists()
    for name in ("Cave", "Ruin"):
        resp = c.post(url("location_create", club, hex_map.pk, 2, -1), {"name": name})
        assert resp.status_code == 302
    assert Location.objects.filter(tile__map=hex_map, tile__q=2, tile__r=-1).count() == 2
    html = c.get(url("detail", club, hex_map.pk)).content.decode()
    assert ">2</text>" in html


@pytest.mark.story("M4")
def test_name_colour_symbol_shown(login, club, hex_map, game_master):
    c = login(game_master)
    data = {"name": "Spire", "color": "blue", "symbol": "S*"}
    c.post(url("location_create", club, hex_map.pk, 1, 1), data)
    tile = c.get(url("tile", club, hex_map.pk, 1, 1)).content.decode()
    assert "Spire" in tile and "blue" in tile and "S*" in tile
    svg = c.get(url("detail", club, hex_map.pk)).content.decode()
    assert "fill: blue" in svg and ">S*</text>" in svg


@pytest.mark.story("M4")
def test_symbol_and_colour_validated(login, club, hex_map, game_master):
    c = login(game_master)
    u = url("location_create", club, hex_map.pk, 1, 1)
    assert c.post(u, {"name": "A", "symbol": "abc"}).status_code == 200
    assert c.post(u, {"name": "A", "color": "pink"}).status_code == 200
    assert not Location.objects.exists()


@pytest.mark.story("M5")
def test_player_notes_visible_gm_notes_hidden(
    login, club, hex_map, game_master, player, player_character
):
    login(game_master).post(
        url("location_create", club, hex_map.pk, 3, 0),
        {"name": "Fort", "player_notes": "Public text", "gm_notes": "Hidden text"},
    )
    record_visits(hex_map, 3, 0, [player_character])
    html = login(player).get(url("tile", club, hex_map.pk, 3, 0)).content.decode()
    assert "Public text" in html and "Hidden text" not in html
    gm = login(game_master).get(url("tile", club, hex_map.pk, 3, 0)).content.decode()
    assert "Hidden text" in gm


@pytest.mark.story("M6")
def test_encounter_add_after_visit_shows_to_player(
    login, club, hex_map, tile_location, game_master, player, player_character
):
    record_visits(hex_map, 1, 0, [player_character])
    login(game_master).post(
        url("encounter_create", club, tile_location.pk),
        {"date": "2025-01-02", "description": "Ambush at dusk"},
    )
    html = login(player).get(url("tile", club, hex_map.pk, 1, 0)).content.decode()
    assert "Ambush at dusk" in html
    assert "edit" not in html.split("Ambush at dusk")[1].split("</li>")[0]


@pytest.mark.story("M6")
def test_encounter_date_default_and_required_description(login, club, tile_location, game_master):
    c = login(game_master)
    u = url("encounter_create", club, tile_location.pk)
    assert c.post(u, {"description": ""}).status_code == 200
    assert not Encounter.objects.exists()
    assert datetime.date.today().isoformat() in c.get(u).content.decode()


@pytest.mark.story("M6")
def test_encounter_edit_delete(login, club, hex_map, encounter, game_master):
    c = login(game_master)
    c.post(url("encounter_edit", club, encounter.pk), {"description": "Bears"})
    encounter.refresh_from_db()
    assert encounter.description == "Bears"
    assert c.get(url("encounter_delete", club, encounter.pk)).status_code == 200
    assert Encounter.objects.exists()
    c.post(url("encounter_delete", club, encounter.pk))
    assert not Encounter.objects.exists()


@pytest.mark.story("M11")
def test_target_band_shown(login, club, hex_map, game_master):
    c = login(game_master)
    c.post(url("location_create", club, hex_map.pk, 4, 0), {"name": "Keep", "target_band": "3-4"})
    assert "CR 3-4" in c.get(url("tile", club, hex_map.pk, 4, 0)).content.decode()


@pytest.mark.story("M3")
def test_location_edit_and_delete_prunes_tile(login, club, hex_map, tile_location, game_master):
    c = login(game_master)
    c.post(url("location_edit", club, tile_location.pk), {"name": "Renamed Tower"})
    tile_location.refresh_from_db()
    assert tile_location.name == "Renamed Tower"
    assert c.get(url("location_delete", club, tile_location.pk)).status_code == 200
    assert Location.objects.exists()
    c.post(url("location_delete", club, tile_location.pk))
    assert not Location.objects.exists()
    assert not Tile.objects.filter(map=hex_map, q=1, r=0).exists()


@pytest.mark.story("M3")
def test_safe_town_not_pruned(login, club, hex_map, game_master):
    c = login(game_master)
    c.post(url("location_create", club, hex_map.pk, 0, 0), {"name": "Inn"})
    loc = Location.objects.get(name="Inn")
    c.post(url("location_delete", club, loc.pk))
    assert Tile.objects.filter(map=hex_map, q=0, r=0, is_safe_town=True).exists()


def _all_urls(club, hex_map, loc, enc):
    return [
        url("map_create", club),
        url("map_edit", club, hex_map.pk),
        url("location_create", club, hex_map.pk, 1, 0),
        url("location_edit", club, loc.pk),
        url("location_delete", club, loc.pk),
        url("encounter_create", club, loc.pk),
        url("encounter_edit", club, enc.pk),
        url("encounter_delete", club, enc.pk),
    ]


@pytest.mark.story("M1")
def test_player_forbidden_everywhere(login, club, hex_map, tile_location, encounter, player):
    c = login(player)
    for u in _all_urls(club, hex_map, tile_location, encounter):
        assert c.get(u).status_code == 403, u
        assert c.post(u, {}).status_code == 403, u


@pytest.mark.story("M1")
def test_cross_club_editor_gets_404(
    login, club, hex_map, tile_location, encounter, other_club_member, other_club
):
    Membership.objects.filter(user=other_club_member).update(is_game_master=True)
    c = login(other_club_member)
    for u in _all_urls(club, hex_map, tile_location, encounter):
        assert c.get(u).status_code == 404, u


@pytest.mark.story("M1")
def test_foreign_pks_404_for_own_gm(login, club, other_map, game_master):
    foreign_tile = Tile.objects.create(map=other_map, q=5, r=5)
    loc = Location.objects.create(tile=foreign_tile, name="Far")
    enc = Encounter.objects.create(location=loc, description="x")
    c = login(game_master)
    for u in (
        url("map_edit", club, other_map.pk),
        url("location_create", club, other_map.pk, 1, 0),
        url("location_edit", club, loc.pk),
        url("location_delete", club, loc.pk),
        url("encounter_create", club, loc.pk),
        url("encounter_edit", club, enc.pk),
        url("encounter_delete", club, enc.pk),
    ):
        assert c.get(u).status_code == 404, u
