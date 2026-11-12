import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Membership
from map.models import LocationCredit, MapRequest, Tile, TileVisit
from map.services import add_to_credit
from player_characters.models import Character

pytestmark = pytest.mark.story("M12")


def _url(name, club, *args):
    return reverse(f"map:{name}", args=[club.slug, *args])


def _visit_post(client, club, hex_map, chars, q=5, r=-3, **extra):
    data = {"q": q, "r": r, "characters": [c.pk for c in chars], "date": "2026-01-02", "note": "n"}
    data.update(extra)
    return client.post(_url("request_visit", club, hex_map.pk), data)


@pytest.fixture
def visit_request(login, club, hex_map, player, character, second_character):
    _visit_post(login(player), club, hex_map, [character, second_character])
    return MapRequest.objects.get()


@pytest.fixture
def visible_location(tile_location, hex_map, character, other_character):
    add_to_credit(tile_location, "discovered", [other_character])
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    return tile_location


def test_player_requests_visit_and_gm_approves(
    login, club, hex_map, player, game_master, character, second_character, visit_request
):
    req = visit_request
    assert req.status == "requested"
    assert (req.q, req.r) == (5, -3)
    assert set(req.characters.all()) == {character, second_character}
    resp = login(game_master).post(_url("request_approve", club, req.pk))
    assert resp.status_code == 302
    req.refresh_from_db()
    assert req.status == "approved"
    assert req.decided_by.user == game_master
    assert req.decided_at is not None
    assert TileVisit.objects.filter(map=hex_map, q=5, r=-3).count() == 2


def test_credit_request_approval(login, club, game_master, player, character, visible_location):
    url = _url("request_credit", club, "discovered", visible_location.pk)
    resp = login(player).post(url, {"characters": [character.pk], "date": "2026-01-02", "note": ""})
    assert resp.status_code == 302
    req = MapRequest.objects.get()
    assert req.kind == "discovered" and req.location == visible_location
    login(game_master).post(_url("request_approve", club, req.pk))
    credit = LocationCredit.objects.get(location=visible_location, kind="discovered")
    assert character in credit.characters.all()
    assert TileVisit.objects.filter(q=1, r=0, character=character).exists()


def test_decline_creates_nothing(login, club, game_master, visit_request):
    login(game_master).post(_url("request_decline", club, visit_request.pk))
    visit_request.refresh_from_db()
    assert visit_request.status == "declined"
    assert visit_request.decided_at is not None
    assert not TileVisit.objects.exists()
    assert not LocationCredit.objects.exists()


def test_cannot_request_for_other_players_character(
    login, club, hex_map, player, other_character, character
):
    _visit_post(login(player), club, hex_map, [other_character])
    assert not MapRequest.objects.exists()
    _visit_post(login(player), club, hex_map, [character, other_character])
    assert not MapRequest.objects.exists()


def test_other_club_character_rejected(login, club, other_club, hex_map, player):
    owner = Membership.objects.create(user=player, club=other_club)
    foreign = Character.objects.create(club=other_club, owner=owner, name="Foreign")
    _visit_post(login(player), club, hex_map, [foreign])
    assert not MapRequest.objects.exists()


def test_player_cannot_decide(login, club, player, visit_request):
    client = login(player)
    assert client.post(_url("request_approve", club, visit_request.pk)).status_code == 403
    assert client.post(_url("request_decline", club, visit_request.pk)).status_code == 403
    visit_request.refresh_from_db()
    assert visit_request.status == "requested"


def test_credit_for_unseen_location_or_bad_kind_404(
    login, club, player, character, other_character, tile_location
):
    add_to_credit(tile_location, "discovered", [other_character])
    client = login(player)
    assert client.get(_url("request_credit", club, "explored", tile_location.pk)).status_code == 404
    TileVisit.objects.create(map=tile_location.tile.map, q=1, r=0, character=character)
    assert client.get(_url("request_credit", club, "bogus", tile_location.pk)).status_code == 404
    assert client.get(_url("request_credit", club, "explored", tile_location.pk)).status_code == 200


def test_deleted_location_only_decline(
    login, club, game_master, player, character, visible_location
):
    login(player).post(
        _url("request_credit", club, "explored", visible_location.pk),
        {"characters": [character.pk], "date": "2026-01-02"},
    )
    req = MapRequest.objects.get()
    visible_location.delete()
    gm = login(game_master)
    page = gm.get(_url("requests", club))
    assert "Location deleted" in page.content.decode()
    assert "Approve</button>" not in page.content.decode()
    gm.post(_url("request_approve", club, req.pk))
    req.refresh_from_db()
    assert req.status == "requested"
    assert not LocationCredit.objects.exists()
    gm.post(_url("request_decline", club, req.pk))
    req.refresh_from_db()
    assert req.status == "declined"


def test_already_decided_not_changed(login, club, game_master, visit_request):
    gm = login(game_master)
    gm.post(_url("request_decline", club, visit_request.pk))
    gm.post(_url("request_approve", club, visit_request.pk))
    visit_request.refresh_from_db()
    assert visit_request.status == "declined"
    assert not TileVisit.objects.exists()


def test_open_requests_stay_open(login, club, hex_map, player, character, visit_request):
    _visit_post(login(player), club, hex_map, [character], q=2, r=2)
    login(player).get(_url("requests", club))
    assert MapRequest.objects.filter(status="requested").count() == 2


def test_queue_order_and_player_scope(
    login, club, hex_map, game_master, player, other_player, character, visit_request
):
    visit_request.status = "declined"
    visit_request.save()
    other_owner = Membership.objects.get(user=other_player, club=club)
    mine = MapRequest.objects.create(
        club=club, kind="visit", map=hex_map, q=9, r=9, requested_by=other_owner
    )
    body = login(game_master).get(_url("requests", club)).content.decode()
    assert body.index("(9, 9)") < body.index("(5, -3)")
    player_body = login(player).get(_url("requests", club)).content.decode()
    assert "(5, -3)" in player_body and "(9, 9)" not in player_body
    assert mine.pk


def test_nav_count(login, club, game_master, player, visit_request):
    assert "Map requests (1)" in login(game_master).get(_url("index", club)).content.decode()
    body = login(player).get(_url("index", club)).content.decode()
    assert "Map requests" in body and "Map requests (" not in body


def test_gm_notes_not_shown_to_player(login, club, player, character, visible_location):
    client = login(player)
    for resp in (
        client.get(_url("requests", club)),
        client.get(_url("request_credit", club, "discovered", visible_location.pk)),
    ):
        assert "Secret GM note" not in resp.content.decode()


def test_cross_club_isolation(
    login, club, other_club, other_map, other_club_member, game_master, visit_request
):
    other_owner = Membership.objects.get(user=other_club_member, club=other_club)
    MapRequest.objects.create(
        club=other_club, kind="visit", map=other_map, q=7, r=7, requested_by=other_owner
    )
    body = login(game_master).get(_url("requests", club)).content.decode()
    assert "(7, 7)" not in body and "(5, -3)" in body
    outsider = login(other_club_member)
    assert outsider.get(_url("requests", club)).status_code == 404
    assert outsider.get(_url("request_visit", club, other_map.pk)).status_code == 404
    gm = login(game_master)
    assert gm.get(_url("request_visit", club, other_map.pk)).status_code == 404
    assert gm.post(_url("request_approve", club, MapRequest.objects.get(q=7).pk)).status_code == 404


def test_other_club_location_404(login, club, other_map, game_master):
    tile = Tile.objects.create(map=other_map, q=1, r=1)
    from map.models import Location

    loc = Location.objects.create(tile=tile, name="Far")
    resp = login(game_master).get(_url("request_credit", club, "discovered", loc.pk))
    assert resp.status_code == 404


def test_demo_one_open_request(club, db):
    from accounts import demo as accounts_demo
    from player_characters import demo as characters_demo

    demo_club = accounts_demo.seed()
    characters_demo.seed(demo_club)
    from map import demo as map_demo

    map_demo.seed(demo_club)
    map_demo.seed(demo_club)
    assert MapRequest.objects.filter(club=demo_club, status="requested").count() == 1
    assert call_command is not None
