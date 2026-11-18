import pytest
from django.urls import reverse

from map.models import FoundMark, LocationCredit, MapRequest, TileVisit
from map.services import add_to_credit

pytestmark = pytest.mark.story("M12")


def _url(club):
    return reverse("map:request_bulk_approve", args=[club.slug])


def _select_url(club, reqs):
    return _url(club) + "?" + "&".join(f"requests={r.pk}" for r in reqs)


def _visit_post(client, club, hex_map, chars, q=5, r=-3, **extra):
    data = {"q": q, "r": r, "characters": [c.pk for c in chars], "date": "2026-01-02", "note": "n"}
    data.update(extra)
    return client.post(reverse("map:request_visit", args=[club.slug, hex_map.pk]), data)


@pytest.fixture
def visit_request(login, club, hex_map, player, character, second_character):
    _visit_post(login(player), club, hex_map, [character, second_character])
    return MapRequest.objects.get()


@pytest.fixture
def visible_location(tile_location, hex_map, character, other_character):
    add_to_credit(tile_location, "discovered", [other_character])
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    return tile_location


@pytest.mark.story("M12")
def test_player_cannot_access_bulk_approve(
    login, club, player, character, second_character, visible_location
):
    client = login(player)
    client.post(
        reverse("map:request_credit", args=[club.slug, "discovered", visible_location.pk]),
        {"characters": [character.pk], "date": "2026-01-02", "note": ""},
    )
    req = MapRequest.objects.get()
    assert client.post(_url(club), {"requests": [req.pk]}).status_code == 403
    assert client.get(_select_url(club, [req])).status_code == 403


@pytest.mark.story("M12")
def test_queue_checkboxes_gm_only(login, club, game_master, player, visit_request):
    gm_body = login(game_master).get(reverse("map:requests", args=[club.slug])).content.decode()
    assert '<input type="checkbox" name="requests"' in gm_body
    assert 'id="bulk-approve-btn"' in gm_body
    player_body = login(player).get(reverse("map:requests", args=[club.slug])).content.decode()
    assert '<input type="checkbox" name="requests"' not in player_body
    assert 'id="bulk-approve-btn"' not in player_body


@pytest.mark.story("M12")
def test_gm_bulk_approve_modal_lists_characters(
    login, club, game_master, player, character, second_character, visible_location
):
    client = login(player)
    client.post(
        reverse("map:request_credit", args=[club.slug, "discovered", visible_location.pk]),
        {"characters": [character.pk], "date": "2026-01-02", "note": "d"},
    )
    client.post(
        reverse("map:request_credit", args=[club.slug, "explored", visible_location.pk]),
        {"characters": [second_character.pk], "date": "2026-01-02", "note": "e"},
    )
    reqs = list(MapRequest.objects.filter(status="requested").order_by("kind"))
    assert {r.kind for r in reqs} == {"discovered", "explored"}

    gm = login(game_master)
    resp = gm.get(_select_url(club, reqs))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Discovery" in body and "Exploration" in body and "Found mark" in body
    assert character.name in body and second_character.name in body


@pytest.mark.story("M12")
def test_gm_bulk_approve_creates_credits_and_marks(
    login, club, game_master, player, character, second_character, visible_location
):
    client = login(player)
    client.post(
        reverse("map:request_credit", args=[club.slug, "discovered", visible_location.pk]),
        {"characters": [character.pk], "date": "2026-01-02", "note": "d"},
    )
    client.post(
        reverse("map:request_credit", args=[club.slug, "explored", visible_location.pk]),
        {"characters": [second_character.pk], "date": "2026-01-02", "note": "e"},
    )
    client.post(
        reverse("map:request_credit", args=[club.slug, "found", visible_location.pk]),
        {"characters": [character.pk], "date": "2026-01-02", "note": "f"},
    )
    reqs = list(MapRequest.objects.filter(status="requested").order_by("kind"))
    assert {r.kind for r in reqs} == {"discovered", "explored", "found"}

    gm = login(game_master)
    resp = gm.post(_url(club), {"requests": [r.pk for r in reqs]}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    trigger = resp["HX-Trigger"]
    assert "appModalClose" in trigger and "refreshQueue" in trigger

    for r in reqs:
        r.refresh_from_db()
        assert r.status == "approved"
        assert r.decided_by.user == game_master
        assert r.decided_at is not None

    assert LocationCredit.objects.filter(
        location=visible_location, kind="discovered", characters=character
    ).exists()
    assert LocationCredit.objects.filter(
        location=visible_location, kind="explored", characters=second_character
    ).exists()
    assert FoundMark.objects.filter(location=visible_location, character=character).exists()


@pytest.mark.story("M12")
def test_explored_credit_created(login, club, game_master, player, character, visible_location):
    client = login(player)
    client.post(
        reverse("map:request_credit", args=[club.slug, "explored", visible_location.pk]),
        {"characters": [character.pk], "date": "2026-01-02", "note": "e"},
    )
    req = MapRequest.objects.get(kind="explored")
    login(game_master).post(_url(club), {"requests": [req.pk]})
    assert LocationCredit.objects.filter(
        location=visible_location, kind="explored", characters=character
    ).exists()


@pytest.mark.story("M12")
def test_visit_excluded_from_bulk_approve(
    login, club, game_master, player, character, hex_map, visit_request
):
    assert visit_request.kind == "visit"
    gm = login(game_master)
    resp = gm.get(_select_url(club, [visit_request]))
    assert resp.status_code == 200
    assert "No approvable requests were selected." in resp.content.decode()
    gm.post(_url(club), {"requests": [visit_request.pk]})
    visit_request.refresh_from_db()
    assert visit_request.status == "requested"
    assert not TileVisit.objects.exists()


@pytest.mark.story("M12")
def test_already_decided_skipped(
    login, club, game_master, player, character, visible_location, visit_request
):
    # Decide one request individually, then include it in a bulk select.
    login(game_master).post(reverse("map:request_approve", args=[club.slug, visit_request.pk]))
    client = login(player)
    client.post(
        reverse("map:request_credit", args=[club.slug, "discovered", visible_location.pk]),
        {"characters": [character.pk], "date": "2026-01-02", "note": "d"},
    )
    credit_req = MapRequest.objects.get(kind="discovered")
    gm = login(game_master)
    resp = gm.post(
        _url(club), {"requests": [visit_request.pk, credit_req.pk]}, HTTP_HX_REQUEST="true"
    )
    assert resp.status_code == 204
    credit_req.refresh_from_db()
    assert credit_req.status == "approved"
    visit_request.refresh_from_db()
    assert visit_request.status == "approved"  # decided individually earlier
