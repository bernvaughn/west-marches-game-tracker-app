import datetime

import pytest
from django.urls import reverse

from accounts.models import Membership, User
from map.models import LocationCredit, Tile, TileVisit
from map.services import add_to_credit, record_visits
from player_characters.models import Character

D = "2026-01-05"


def visits_url(hex_map, q=1, r=0, club="club-a"):
    return reverse("map:visits", args=[club, hex_map.pk, q, r])


def credit_url(location, kind="discovered", club="club-a"):
    return reverse("map:credit", args=[club, location.pk, kind])


@pytest.fixture
def foreign_gm(other_club):
    user = User.objects.create_user("fgm@example.com", password="pw", display_name="FGM")
    Membership.objects.create(user=user, club=other_club, is_game_master=True)
    return user


@pytest.fixture
def foreign_character(other_club, foreign_gm):
    owner = Membership.objects.get(user=foreign_gm, club=other_club)
    return Character.objects.create(club=other_club, owner=owner, name="Zed Foreign")


def ids(*chars):
    return [c.pk for c in chars]


@pytest.mark.story("M7")
def test_one_post_records_three_and_repeat_adds_none(
    login, game_master, hex_map, character, second_character, other_character
):
    c = login(game_master)
    data = {
        "action": "add",
        "characters": ids(character, second_character, other_character),
        "date": D,
    }
    assert c.post(visits_url(hex_map), data).status_code == 302
    assert TileVisit.objects.filter(map=hex_map, q=1, r=0).count() == 3
    c.post(visits_url(hex_map), data)
    assert TileVisit.objects.filter(map=hex_map).count() == 3
    assert TileVisit.objects.first().date == datetime.date(2026, 1, 5)


@pytest.mark.story("M7")
def test_empty_position_can_be_visited(login, game_master, hex_map, character):
    c = login(game_master)
    url = visits_url(hex_map, 3, -2)
    c.post(url, {"action": "add", "characters": ids(character), "date": D})
    assert TileVisit.objects.filter(map=hex_map, q=3, r=-2).count() == 1
    assert not Tile.objects.filter(map=hex_map, q=3, r=-2).exists()
    assert "Aria" in c.get(url).content.decode()


@pytest.mark.story("M7")
def test_no_characters_saves_nothing(login, game_master, hex_map):
    r = login(game_master).post(visits_url(hex_map), {"action": "add", "date": D})
    assert r.status_code == 200
    assert "Pick at least one character" in r.content.decode()
    assert TileVisit.objects.count() == 0


@pytest.mark.story("M7")
def test_editor_removes_visit(login, club_admin, hex_map, character, second_character):
    record_visits(hex_map, 1, 0, [character])
    record_visits(hex_map, 2, 0, [second_character])
    other = TileVisit.objects.get(q=2)
    mine = TileVisit.objects.get(q=1)
    c = login(club_admin)
    assert (
        c.post(visits_url(hex_map), {"action": "remove", "visit_id": other.pk}).status_code == 404
    )
    assert c.post(visits_url(hex_map), {"action": "remove", "visit_id": mine.pk}).status_code == 302
    assert not TileVisit.objects.filter(pk=mine.pk).exists()
    assert TileVisit.objects.filter(pk=other.pk).exists()


@pytest.mark.story("M7")
def test_player_forbidden_on_visits(login, player, hex_map, character):
    c = login(player)
    assert c.get(visits_url(hex_map)).status_code == 403
    r = c.post(visits_url(hex_map), {"action": "add", "characters": ids(character), "date": D})
    assert r.status_code == 403
    assert TileVisit.objects.count() == 0


@pytest.mark.story("M7")
def test_tile_page_link_for_gm_only(login, game_master, player, hex_map, tile_location):
    url = reverse("map:tile", args=["club-a", hex_map.pk, 1, 0])
    assert "Record visits" in login(game_master).get(url).content.decode()
    record_visits(hex_map, 1, 0, [])
    assert (
        "Record visits"
        not in login(player)
        .get(reverse("map:tile", args=["club-a", hex_map.pk, 0, 0]))
        .content.decode()
    )


@pytest.mark.story("M14")
def test_first_discovered_group_stored_with_visits(
    login, game_master, hex_map, tile_location, character, second_character
):
    c = login(game_master)
    r = c.post(
        credit_url(tile_location),
        {"action": "add", "characters": ids(character, second_character), "date": D},
    )
    assert r.status_code == 302
    credit = LocationCredit.objects.get(location=tile_location, kind="discovered")
    assert set(credit.characters.all()) == {character, second_character}
    assert credit.date == datetime.date(2026, 1, 5)
    assert TileVisit.objects.filter(map=hex_map, q=1, r=0).count() == 2
    assert (
        "Edit discovered"
        in c.get(reverse("map:tile", args=["club-a", hex_map.pk, 1, 0])).content.decode()
    )


@pytest.mark.story("M14")
def test_later_visit_does_not_add_to_credit(hex_map, tile_location, character, second_character):
    add_to_credit(tile_location, "discovered", [character])
    record_visits(hex_map, 1, 0, [second_character])
    credit = LocationCredit.objects.get(location=tile_location)
    assert list(credit.characters.all()) == [character]


@pytest.mark.story("M14")
def test_editor_adds_and_removes_explored(
    login, club_admin, tile_location, character, second_character
):
    c = login(club_admin)
    url = credit_url(tile_location, "explored")
    c.post(url, {"action": "add", "characters": ids(character, second_character), "date": D})
    assert "Borin" in c.get(url).content.decode()
    c.post(url, {"action": "remove", "characters": ids(second_character)})
    credit = LocationCredit.objects.get(location=tile_location, kind="explored")
    assert list(credit.characters.all()) == [character]


@pytest.mark.story("M14")
def test_removing_last_character_clears_credit_keeps_visits(
    login, game_master, hex_map, tile_location, character
):
    c = login(game_master)
    url = credit_url(tile_location, "explored")
    c.post(url, {"action": "add", "characters": ids(character), "date": D})
    c.post(url, {"action": "remove", "characters": ids(character)})
    assert not LocationCredit.objects.filter(location=tile_location, kind="explored").exists()
    assert TileVisit.objects.filter(map=hex_map, q=1, r=0).count() == 1


@pytest.mark.story("M14")
def test_bad_kind_404_and_player_403(login, game_master, player, tile_location):
    assert login(game_master).get(credit_url(tile_location, "bogus")).status_code == 404
    c = login(player)
    assert c.get(credit_url(tile_location)).status_code == 403
    assert c.post(credit_url(tile_location), {"action": "add", "date": D}).status_code == 403


@pytest.mark.story("M7")
def test_foreign_character_not_recorded_on_visits(login, game_master, hex_map, foreign_character):
    login(game_master).post(
        visits_url(hex_map), {"action": "add", "characters": ids(foreign_character), "date": D}
    )
    assert TileVisit.objects.count() == 0


@pytest.mark.story("M14")
def test_foreign_character_not_added_to_credit(
    login, game_master, tile_location, foreign_character, character
):
    c = login(game_master)
    c.post(
        credit_url(tile_location),
        {"action": "add", "characters": ids(foreign_character, character), "date": D},
    )
    credit = LocationCredit.objects.get(location=tile_location)
    assert list(credit.characters.all()) == [character]
    assert "Zed Foreign" not in c.get(credit_url(tile_location)).content.decode()
    assert "Zed Foreign" not in c.get(visits_url(tile_location.tile.map)).content.decode()


@pytest.mark.story("M7")
def test_cross_club_visits_404(login, foreign_gm, hex_map, other_map):
    c = login(foreign_gm)
    assert c.get(visits_url(hex_map)).status_code == 404
    assert c.get(visits_url(hex_map, club="club-b")).status_code == 404
    assert c.get(visits_url(other_map, club="club-b")).status_code == 200


@pytest.mark.story("M14")
def test_cross_club_credit_404(login, foreign_gm, tile_location):
    c = login(foreign_gm)
    assert c.get(credit_url(tile_location)).status_code == 404
    assert c.get(credit_url(tile_location, club="club-b")).status_code == 404
