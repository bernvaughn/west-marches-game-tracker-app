import pytest
from django.urls import reverse

pytestmark = pytest.mark.story("FOUNDATION")

ROUTES = [
    "club_home",
    "accounts:index",
    "characters:directory",
    "items:index",
    "shops:index",
    "ledger:index",
    "map:index",
    "quests:index",
    "agent_access:index",
]


@pytest.mark.parametrize("route", ROUTES)
def test_member_gets_404_on_other_club(route, login, player, other_club):
    resp = login(player).get(reverse(route, args=[other_club.slug]))
    assert resp.status_code == 404


@pytest.mark.parametrize("route", ROUTES)
def test_site_admin_enters_both_clubs(route, login, site_admin, club, other_club):
    client = login(site_admin)
    for c in (club, other_club):
        assert client.get(reverse(route, args=[c.slug])).status_code == 200


def test_unknown_club_404(login, player):
    assert login(player).get("/c/nope/").status_code == 404


def test_anonymous_redirected_to_login(client, club):
    resp = client.get(reverse("club_home", args=[club.slug]))
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


def test_for_club_filters_child_models(club, other_club, player, character):
    from map.models import HexMap, Tile

    HexMap.objects.create(club=club, name="M1")
    HexMap.objects.create(club=other_club, name="M2")
    assert Tile.objects.for_club(club).count() == 1
