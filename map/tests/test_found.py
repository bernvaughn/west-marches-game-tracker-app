import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Membership
from map.models import FoundMark, Location, MapRequest, Tile, TileVisit
from map.services import add_found_marks, add_to_credit, record_visits
from map.visibility import found_location_ids, placeholder_location_ids
from player_characters.models import Character


def url(name, club, *args):
    return reverse(f"map:{name}", args=[club.slug, *args])


@pytest.fixture
def secret(tile_location, hex_map):
    """The watchtower, discovered by Cael only, with extras that must not leak."""
    tile_location.encounters.create(description="Wyvern ambush")
    return tile_location


@pytest.fixture
def placeholder_world(secret, hex_map, player_character, other_character):
    add_to_credit(secret, "discovered", [other_character])
    record_visits(hex_map, 1, 0, [player_character])
    return secret


@pytest.fixture
def undiscovered(hex_map, player_character):
    tile = Tile.objects.create(map=hex_map, q=0, r=2)
    loc = Location.objects.create(
        tile=tile, name="Buried Vault", symbol="V", player_notes="Vault note", target_band="9-10"
    )
    record_visits(hex_map, 0, 2, [player_character])
    return loc


@pytest.mark.story("M16")
def test_found_ids_from_credit_and_mark(secret, player_character, second_character):
    assert found_location_ids([player_character]) == set()
    assert found_location_ids([]) == set()
    add_to_credit(secret, "explored", [player_character])
    assert found_location_ids([player_character]) == {secret.pk}
    add_found_marks(secret, [second_character])
    assert found_location_ids([second_character]) == {secret.pk}


@pytest.mark.story("M16")
def test_placeholder_ids(placeholder_world, undiscovered, hex_map, player_character):
    pos = {(1, 0), (0, 2), (0, 0)}
    assert placeholder_location_ids(hex_map, pos, set()) == {placeholder_world.pk}
    assert placeholder_location_ids(hex_map, pos, {placeholder_world.pk}) == set()
    assert placeholder_location_ids(hex_map, {(0, 2)}, set()) == set()


@pytest.mark.story("M16")
def test_map_shows_placeholder_and_hides_undiscovered(
    login, club, hex_map, player, placeholder_world, undiscovered
):
    resp = login(player).get(url("detail", club, hex_map.pk))
    body = resp.content.decode()
    assert "hex-unknown" in body
    cells = {(c["q"], c["r"]): c for c in resp.context["cells"]}
    assert cells[(1, 0)]["count"] == 1 and cells[(1, 0)]["unknown"] == 1
    assert cells[(0, 2)]["count"] == 0 and cells[(0, 2)]["unknown"] == 0
    assert cells[(0, 2)]["visited"] and not cells[(0, 2)]["fill"]
    for text in ["Old Watchtower", "Buried Vault", "Player note", "Wyvern", "CR 1-2"]:
        assert text not in body
    assert cells[(1, 0)]["symbol"] == ""


@pytest.mark.story("M16")
def test_map_shows_found_in_full(login, club, hex_map, player, placeholder_world, player_character):
    add_found_marks(placeholder_world, [player_character])
    resp = login(player).get(url("detail", club, hex_map.pk))
    cell = {(c["q"], c["r"]): c for c in resp.context["cells"]}[(1, 0)]
    assert cell["symbol"] == "T" and cell["count"] == 1 and cell["unknown"] == 0
    assert "hex-unknown" not in resp.content.decode()


@pytest.mark.story("M16")
def test_tile_page_lists_unknown_location(
    login, club, hex_map, player, placeholder_world, other_character
):
    body = login(player).get(url("tile", club, hex_map.pk, 1, 0)).content.decode()
    assert "Unknown location" in body
    for kind in ["found", "explored", "discovered"]:
        assert url("request_credit", club, kind, placeholder_world.pk) in body
    for text in [
        "Old Watchtower",
        "Player note text",
        "Wyvern",
        "CR 1-2",
        "Cael",
        "Colour",
        "Secret GM note",
        "/edit/",
    ]:
        assert text not in body
    assert "Nothing here yet" not in body


@pytest.mark.story("M16")
def test_tile_page_undiscovered_absent(login, club, hex_map, player, undiscovered):
    body = login(player).get(url("tile", club, hex_map.pk, 0, 2)).content.decode()
    assert "Buried Vault" not in body and "Unknown location" not in body
    assert "Nothing here yet" in body
    assert f"location/{undiscovered.pk}/" not in body


@pytest.mark.story("M16")
def test_tile_page_found_in_full(login, club, hex_map, player, placeholder_world, player_character):
    add_found_marks(placeholder_world, [player_character])
    body = login(player).get(url("tile", club, hex_map.pk, 1, 0)).content.decode()
    assert "Old Watchtower" in body and "Wyvern" in body and "Unknown location" not in body


@pytest.mark.story("M16")
def test_editor_full_view_unchanged(
    login, club, hex_map, game_master, placeholder_world, undiscovered
):
    client = login(game_master)
    body = client.get(url("tile", club, hex_map.pk, 1, 0)).content.decode()
    assert "Old Watchtower" in body and "Wyvern" in body and "Unknown location" not in body
    resp = client.get(url("detail", club, hex_map.pk))
    cells = {(c["q"], c["r"]): c for c in resp.context["cells"]}
    assert cells[(0, 2)]["count"] == 1 and cells[(1, 0)]["symbol"] == "T"
    assert "Old Watchtower" in client.get(url("print", club, hex_map.pk)).content.decode()


@pytest.mark.story("M10")
def test_gm_players_view_follows_rules(
    login, club, hex_map, game_master, placeholder_world, undiscovered, player_character
):
    q = f"?view=players&characters={player_character.pk}"
    client = login(game_master)
    body = client.get(url("tile", club, hex_map.pk, 1, 0) + q).content.decode()
    assert "Unknown location" in body and "Old Watchtower" not in body
    printed = client.get(url("print", club, hex_map.pk) + q).content.decode()
    assert "Old Watchtower" not in printed and "Buried Vault" not in printed


@pytest.mark.story("M5")
def test_print_placeholder(login, club, hex_map, player, placeholder_world, undiscovered):
    body = login(player).get(url("print", club, hex_map.pk)).content.decode()
    assert "? Unknown location (1, 0)" in body
    for text in ["Old Watchtower", "Buried Vault", "Wyvern", "Player note", "Cael", "CR 1-2"]:
        assert text not in body


@pytest.mark.story("M5")
def test_print_found(login, club, hex_map, player, placeholder_world, player_character):
    add_found_marks(placeholder_world, [player_character])
    body = login(player).get(url("print", club, hex_map.pk)).content.decode()
    assert "Old Watchtower" in body and "Unknown location" not in body


@pytest.mark.story("M16")
def test_found_page_add_remove(
    login, club, hex_map, game_master, club_admin, secret, player_character
):
    page = url("found", club, secret.pk)
    for user in [game_master, club_admin]:
        client = login(user)
        assert client.get(page).status_code == 200
        client.post(
            page, {"action": "add", "characters": [player_character.pk], "date": "2026-02-03"}
        )
        mark = FoundMark.objects.get()
        assert mark.date.isoformat() == "2026-02-03"
        assert mark.created_by.user == user
        assert TileVisit.objects.filter(character=player_character, q=1, r=0).exists()
        client.post(page, {"action": "remove", "characters": [player_character.pk]})
        assert not FoundMark.objects.exists()


@pytest.mark.story("M16")
def test_found_page_player_refused(login, club, player, secret, player_character):
    client = login(player)
    page = url("found", club, secret.pk)
    assert client.get(page).status_code == 403
    resp = client.post(
        page, {"action": "add", "characters": [player_character.pk], "date": "2026-02-03"}
    )
    assert resp.status_code == 403
    assert not FoundMark.objects.exists()


@pytest.mark.story("M16")
def test_found_page_isolation(
    login, club, other_club, game_master, secret, other_club_member, club_admin
):

    Membership.objects.filter(user=other_club_member).update(is_game_master=True)
    other_char = Character.objects.create(
        club=other_club, owner=Membership.objects.get(user=other_club_member), name="Zed"
    )
    # Another club's GM cannot reach the location through their own club.
    resp = login(other_club_member).get(url("found", other_club, secret.pk))
    assert resp.status_code == 404
    # A foreign character is ignored.
    login(game_master).post(
        url("found", club, secret.pk),
        {"action": "add", "characters": [other_char.pk], "date": "2026-02-03"},
    )
    assert not FoundMark.objects.exists()


@pytest.mark.story("M12")
def test_found_request_approval_creates_marks(
    login, club, game_master, player, placeholder_world, player_character
):
    page = url("request_credit", club, "found", placeholder_world.pk)
    assert "Unknown location" in login(player).get(page).content.decode()
    assert "Old Watchtower" not in login(player).get(page).content.decode()
    resp = login(player).post(
        page, {"characters": [player_character.pk], "date": "2026-01-02", "note": ""}
    )
    assert resp.status_code == 302
    req = MapRequest.objects.get()
    assert req.kind == "found"
    queue = login(player).get(url("requests", club)).content.decode()
    assert "Old Watchtower" not in queue and "Unknown location" in queue
    login(game_master).post(url("request_approve", club, req.pk))
    mark = FoundMark.objects.get()
    assert mark.character == player_character and mark.created_by.user == game_master
    queue = login(player).get(url("requests", club)).content.decode()
    assert "Old Watchtower" in queue


@pytest.mark.story("M12")
@pytest.mark.parametrize("kind", ["found", "explored", "discovered"])
def test_placeholder_accepts_all_kinds(login, club, player, placeholder_world, kind):
    page = url("request_credit", club, kind, placeholder_world.pk)
    assert login(player).get(page).status_code == 200


@pytest.mark.story("M12")
def test_no_first_discovery_request(login, club, player, game_master, undiscovered):
    for user in [player, game_master]:
        for kind in ["found", "explored", "discovered"]:
            page = url("request_credit", club, kind, undiscovered.pk)
            assert login(user).get(page).status_code == 404


@pytest.mark.story("M12")
def test_request_on_unvisited_tile_404(login, club, player, secret, other_character):
    add_to_credit(secret, "discovered", [other_character])
    assert login(player).get(url("request_credit", club, "found", secret.pk)).status_code == 404


@pytest.mark.story("M12")
def test_request_pages_isolation(login, club, other_club, other_club_member, placeholder_world):
    for name in ["found", "explored"]:
        page = url("request_credit", club, name, placeholder_world.pk)
        assert login(other_club_member).get(page).status_code in (403, 404)
    page = url("request_credit", other_club, "found", placeholder_world.pk)
    assert login(other_club_member).get(page).status_code == 404


@pytest.mark.story("M16")
def test_cross_club_pages(login, club, other_club, hex_map, other_club_member, secret):
    c = login(other_club_member)
    for name, args in [
        ("detail", (hex_map.pk,)),
        ("tile", (hex_map.pk, 1, 0)),
        ("print", (hex_map.pk,)),
    ]:
        assert c.get(url(name, club, *args)).status_code in (403, 404)
        assert c.get(url(name, other_club, *args)).status_code == 404


@pytest.mark.story("M16")
@pytest.mark.django_db
def test_demo_placeholder_and_hidden():
    from accounts.models import User
    from map.models import HexMap

    call_command("seed_demo")
    call_command("seed_demo")
    from django.test import Client

    hex_map = HexMap.objects.get()
    club = hex_map.club

    def body(email, name, *args):
        c = Client()
        c.force_login(User.objects.get(email=email))
        return c.get(url(name, club, hex_map.pk, *args))

    emails = {u.display_name: u.email for u in User.objects.all()}
    bob = body(emails["Bob"], "detail")
    assert "hex-unknown" in bob.content.decode()
    cells = {(c["q"], c["r"]): c for c in bob.context["cells"]}
    assert cells[(1, 0)]["unknown"] == 1
    alice = body(emails["Alice"], "detail")
    assert "Wolf Den" not in alice.content.decode()
    assert body(emails["Alice"], "tile", 0, -2).status_code in (200, 404)
    assert "Wolf Den" not in body(emails["Alice"], "tile", 0, -2).content.decode()
