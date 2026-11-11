import pytest
from django.urls import reverse

from accounts.models import Club
from map.models import Location, XPLevel
from map.xp import DEFAULT_XP_TABLE, band_label, xp_for

m13 = pytest.mark.story("M13")
m11 = pytest.mark.story("M11")


def xp_url(club):
    return reverse("map:xp", args=[club.slug])


def payload(**over):
    data = {}
    for band, d, e in DEFAULT_XP_TABLE:
        data[f"discover_{band}"] = d
        data[f"explore_{band}"] = e
    data.update(over)
    return data


def tile_url(hex_map, club):
    return reverse("map:tile", args=[club.slug, hex_map.pk, 1, 0])


@m13
def test_new_club_gets_default_table(db):
    c = Club.objects.create(name="New", slug="new")
    assert XPLevel.objects.filter(club=c).count() == 10
    row = XPLevel.objects.get(club=c, band="17-18")
    assert (row.discover_xp, row.explore_xp) == (17500, 52000)


@m13
def test_lazy_copy(login, club, player):
    XPLevel.objects.filter(club=club).delete()
    r = login(player).get(xp_url(club))
    assert r.status_code == 200
    assert XPLevel.objects.filter(club=club).count() == 10


@m13
def test_order(login, club, player):
    html = login(player).get(xp_url(club)).content.decode()
    assert html.index("CR 3-4") < html.index("CR 11-12") < html.index("CR 19-20")
    assert 'name="discover_' not in html


@m13
def test_admin_saves(login, club, club_admin):
    r = login(club_admin).post(xp_url(club), payload(**{"discover_1-2": 100, "explore_1-2": 300}))
    assert r.status_code == 302
    row = XPLevel.objects.get(club=club, band="1-2")
    assert (row.discover_xp, row.explore_xp) == (100, 300)


@m13
def test_site_admin_saves(login, club, site_admin):
    from accounts.models import Membership  # noqa: F401

    r = login(site_admin).post(xp_url(club), payload(**{"discover_1-2": 1}))
    assert r.status_code == 302


@m13
def test_gm_and_player_cannot_save(login, club, game_master, player):
    for user in (game_master, player):
        assert login(user).post(xp_url(club), payload(**{"discover_1-2": 1})).status_code == 403
    assert XPLevel.objects.get(club=club, band="1-2").discover_xp == 75
    html = login(game_master).get(xp_url(club)).content.decode()
    assert 'name="discover_' not in html and "Save" not in html


@m13
def test_invalid_values(login, club, club_admin):
    for bad in ("-1", "abc", ""):
        r = login(club_admin).post(xp_url(club), payload(**{"discover_1-2": bad}))
        assert r.status_code == 200
    assert XPLevel.objects.get(club=club, band="1-2").discover_xp == 75


@m13
def test_edit_isolated(login, club, other_club, club_admin):
    login(club_admin).post(xp_url(club), payload(**{"discover_1-2": 5}))
    assert XPLevel.objects.get(club=other_club, band="1-2").discover_xp == 75


@m13
def test_cross_club_404(login, club, other_club_member):
    c = login(other_club_member)
    assert c.get(xp_url(club)).status_code == 404
    assert c.post(xp_url(club), payload()).status_code == 404


@m11
def test_tile_shows_xp(login, club, hex_map, tile_location, game_master):
    c = login(game_master)
    assert "Discover 75 XP, explore 225 XP" in c.get(tile_url(hex_map, club)).content.decode()
    XPLevel.objects.filter(club=club, band="1-2").update(discover_xp=80)
    assert "Discover 80 XP, explore 225 XP" in c.get(tile_url(hex_map, club)).content.decode()


@m11
def test_empty_band_shows_nothing(login, club, hex_map, tile_location, game_master):
    Location.objects.filter(pk=tile_location.pk).update(target_band="")
    assert " XP" not in login(game_master).get(tile_url(hex_map, club)).content.decode()


@m11
def test_helpers(club):
    assert band_label("1-2") == "CR 1-2"
    assert band_label("") == ""
    assert xp_for(club, "1-2") == (75, 225)
    assert xp_for(club, "") is None


@m11
def test_tile_cross_club_404(login, club, hex_map, tile_location, other_club_member):
    assert login(other_club_member).get(tile_url(hex_map, club)).status_code == 404
