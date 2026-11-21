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


def test_queue_summary_cell_has_character_kind_position_status(
    login, club, game_master, hex_map, player
):
    """Phone summary cell holds character, kind, (q, r) and status."""
    owner = Membership.objects.get(user=player, club=club)
    req = _create_request(club, hex_map, owner, 5, 9)
    body = login(game_master).get(_url(club)).content.decode()
    assert "wm-req-summary" in body
    assert "Visit" in body
    assert "(5, 9)" in body
    assert req.get_status_display() in body


def test_queue_header_checkbox_has_wm_check_sm(login, club, game_master, hex_map, player):
    """Header checkbox has wm-check-sm class."""
    owner = Membership.objects.get(user=player, club=club)
    _create_request(club, hex_map, owner, 1, 1)
    body = login(game_master).get(_url(club)).content.decode()
    soup = BeautifulSoup(body, "html.parser")
    header_box = soup.select_one("#bulk-select-all")
    assert header_box is not None
    assert "wm-check-sm" in header_box.get("class", [])


def test_queue_checkbox_cells_are_visible_on_desktop(login, club, game_master, hex_map, player):
    """Checkbox th and td must not carry d-sm-none, which would hide them at 576 px and wider."""
    owner = Membership.objects.get(user=player, club=club)
    _create_request(club, hex_map, owner, 1, 1)
    body = login(game_master).get(_url(club)).content.decode()
    soup = BeautifulSoup(body, "html.parser")
    head_cell = soup.select_one("#bulk-select-all").find_parent(["th", "td"])
    row_cell = soup.select_one("input[name=requests]").find_parent(["th", "td"])
    for cell in (head_cell, row_cell):
        assert "d-sm-none" not in cell.get("class", [])
    # Header and row boxes share one size class and sit in a label with tap padding.
    assert "wm-check-sm" in soup.select_one("input[name=requests]").get("class", [])
    assert soup.select_one("input[name=requests]").find_parent("label") is not None
