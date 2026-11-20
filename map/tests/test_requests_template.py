import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from accounts.models import Membership, User
from map.models import MapRequest

pytestmark = pytest.mark.story("M12")


def _url(club):
    return reverse("map:requests", args=[club.slug])


def _create_request(club, hex_map, owner, q, r):
    return MapRequest.objects.create(
        club=club,
        kind="visit",
        map=hex_map,
        q=q,
        r=r,
        requested_by=owner,
        status="requested",
    )


def _scripts(html):
    return BeautifulSoup(html, "html.parser").find_all("script")


def test_queue_has_no_inline_script(login, club, game_master, hex_map, player):
    owner = Membership.objects.get(user=player, club=club)
    _create_request(club, hex_map, owner, 1, 1)
    body = login(game_master).get(_url(club)).content.decode()
    assert all(script.get("src") for script in _scripts(body))


def test_queue_loads_bulk_js_with_defer(login, club, game_master, hex_map, player):
    owner = Membership.objects.get(user=player, club=club)
    _create_request(club, hex_map, owner, 1, 1)
    body = login(game_master).get(_url(club)).content.decode()
    bulk = [s for s in _scripts(body) if "map_request_bulk.js" in (s.get("src") or "")]
    assert len(bulk) == 1
    assert bulk[0].has_attr("defer")


def test_queue_row_checkboxes_named(login, club, game_master, hex_map, player):
    alice = Membership.objects.get(user=player, club=club)
    bea_user = User.objects.create_user("bea@example.com", password="pw", display_name="Bea")
    bea = Membership.objects.create(user=bea_user, club=club)
    _create_request(club, hex_map, alice, 1, 1)
    _create_request(club, hex_map, bea, 2, 2)
    body = login(game_master).get(_url(club)).content.decode()
    soup = BeautifulSoup(body, "html.parser")
    boxes = soup.select('input[name="requests"]')
    assert len(boxes) == 2
    labels = {box.get("aria-label") for box in boxes}
    assert "Select request from Player" in labels
    assert "Select request from Bea" in labels
