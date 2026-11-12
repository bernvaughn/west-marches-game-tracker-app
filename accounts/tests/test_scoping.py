import pytest
from django.urls import reverse

from accounts.models import Membership
from player_characters.models import Trade, TradeLine

pytestmark = pytest.mark.story("FOUNDATION")

ROUTES = [
    "club_home",
    "accounts:index",
    "characters:directory",
    "trades:index",
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

    other_owner = Membership.objects.create(user=player, club=other_club)
    from player_characters.models import Character

    other_char = Character.objects.create(club=other_club, owner=other_owner, name="Zed")
    t1 = Trade.objects.create(club=club, sender=character, receiver=character)
    t2 = Trade.objects.create(club=other_club, sender=other_char, receiver=other_char)
    TradeLine.objects.create(trade=t1)
    TradeLine.objects.create(trade=t2)
    assert TradeLine.objects.for_club(club).count() == 1
    HexMap.objects.create(club=club, name="M1")
    HexMap.objects.create(club=other_club, name="M2")
    assert Tile.objects.for_club(club).count() == 1
