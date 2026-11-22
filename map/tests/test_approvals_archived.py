"""Tests for archived character markers on map approval queues (U146)."""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from map.approvals import open_map_requests
from map.models import Location, MapRequest, Tile, TileVisit
from player_characters.models import Character

pytestmark = pytest.mark.story("M12")


def _url(name, club, *args):
    return reverse(f"map:{name}", args=[club.slug, *args])


def _archive(character):
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])


def _visit_post(client, club, hex_map, chars, q=5, r=-3, **extra):
    data = {
        "q": q,
        "r": r,
        "characters": [c.pk for c in chars],
        "date": "2026-01-02",
        "note": "n",
    }
    data.update(extra)
    return client.post(_url("request_visit", club, hex_map.pk), data)


def test_queue_shows_archived_for_visit_request(
    login, club, player, game_master, hex_map, character, second_character
):
    """A pending visit request from an archived character shows "Archived" on the queue."""
    _visit_post(login(player), club, hex_map, [character, second_character])
    MapRequest.objects.get()
    _archive(character)

    page = login(game_master).get(_url("requests", club)).content.decode()
    assert ">Archived<" in page


def test_queue_shows_archived_for_credit_request(login, club, player, game_master, hex_map):
    """A pending credit request from an archived character shows "Archived" on the queue."""
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(
        tile=tile,
        name="Test Location",
        color="red",
        symbol="T",
    )
    owner = Membership.objects.get(user=player, club=hex_map.club)
    archived_char = Character.objects.create(
        club=hex_map.club, owner=owner, name="Archived Credit Char", archived_at=timezone.now()
    )
    MapRequest.objects.create(
        club=hex_map.club,
        kind=MapRequest.Kind.DISCOVERED,
        location=location,
        tile=tile,
        map=tile.map,
        q=tile.q,
        r=tile.r,
        date="2026-01-02",
        note="n",
        requested_by=owner,
    )
    req = MapRequest.objects.get()
    req.characters.add(archived_char)

    page = login(game_master).get(_url("requests", club)).content.decode()
    assert ">Archived<" in page


def test_queue_shows_living_character_without_marker(
    login, club, player, game_master, hex_map, character, second_character
):
    """A living character shows no "Archived" marker on the queue."""
    _visit_post(login(player), club, hex_map, [character, second_character])

    page = login(game_master).get(_url("requests", club)).content.decode()
    assert ">Archived<" not in page


def test_gm_can_approve_archived_character_visit_request(
    login, club, player, game_master, hex_map, character, second_character
):
    """GM can still approve a pending visit request from an archived character."""
    _visit_post(login(player), club, hex_map, [character, second_character])
    req = MapRequest.objects.get()
    _archive(character)

    resp = login(game_master).post(_url("request_approve", club, req.pk))
    assert resp.status_code == 302

    req.refresh_from_db()
    assert req.status == "approved"
    assert TileVisit.objects.filter(map=hex_map, q=5, r=-3).count() == 2


def test_gm_can_decline_archived_character_visit_request(
    login, club, player, game_master, hex_map, character
):
    """GM can still decline a pending visit request from an archived character."""
    _visit_post(login(player), club, hex_map, [character])
    req = MapRequest.objects.get()
    _archive(character)

    resp = login(game_master).post(_url("request_decline", club, req.pk))
    assert resp.status_code == 302

    req.refresh_from_db()
    assert req.status == "declined"
    assert not TileVisit.objects.exists()


def test_bulk_approve_can_approve_archived_character_request(
    login, club, player, game_master, hex_map
):
    """Bulk approve can approve a credit request from an archived character."""
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(
        tile=tile,
        name="Bulk Test Location",
        color="red",
        symbol="T",
    )
    owner = Membership.objects.get(user=player, club=hex_map.club)
    archived_char = Character.objects.create(
        club=hex_map.club, owner=owner, name="Bulk Archived Char", archived_at=timezone.now()
    )
    MapRequest.objects.create(
        club=hex_map.club,
        kind=MapRequest.Kind.DISCOVERED,
        location=location,
        tile=tile,
        map=tile.map,
        q=tile.q,
        r=tile.r,
        date="2026-01-02",
        note="n",
        requested_by=owner,
    )
    req = MapRequest.objects.get()
    req.characters.add(archived_char)

    client = login(game_master)
    resp = client.post(
        _url("request_bulk_approve", club),
        {"requests": [str(req.pk)]},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204

    req.refresh_from_db()
    assert req.status == "approved"


def test_nav_count_includes_archived_request(
    login, rf, club, player, game_master, hex_map, character
):
    """The navbar open_map_requests count still includes requests from
    archived characters."""
    _visit_post(login(player), club, hex_map, [character])
    _archive(character)

    def req_for(user):
        r = rf.get("/")
        r.user, r.club = user, club
        r.membership = user.memberships.filter(club=club).first()
        return r

    assert open_map_requests(req_for(game_master))[1] >= 1


def test_queue_mixed_living_and_archived_character(
    login, club, player, game_master, hex_map, character
):
    """A request with one living and one archived character shows the marker
    for the archived one."""
    owner = character.owner
    archived_char = Character.objects.create(
        club=club, owner=owner, name="Archived Char", archived_at=timezone.now()
    )
    Tile.objects.create(map=hex_map, q=1, r=0)
    MapRequest.objects.create(
        club=club,
        kind=MapRequest.Kind.VISIT,
        map=hex_map,
        q=1,
        r=0,
        date="2026-01-02",
        note="n",
        requested_by=owner,
    )
    req = MapRequest.objects.get()
    req.characters.add(character, archived_char)

    page = login(game_master).get(_url("requests", club)).content.decode()
    assert ">Archived<" in page
    assert archived_char.name in page
