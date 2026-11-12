import re

import pytest
from django.urls import reverse

from map.models import XPLevel

pytestmark = [pytest.mark.django_db, pytest.mark.story("U43")]

NOT_FOR_YOU = ("Agent tools are for game masters.", "Only club members can send messages.")


def tile_hrefs(body):
    return re.findall(r'wm-area-card"><a[^>]*href="([^"]+)"', body)


@pytest.mark.parametrize("who", ["player", "game_master", "club_admin"])
def test_every_tile_opens_without_lock(who, request, login, club, character):
    user = request.getfixturevalue(who)
    c = login(user)
    body = c.get(reverse("club_home", args=[club.slug])).content.decode()
    links = tile_hrefs(body)
    assert links
    agent = reverse("agent_access:index", args=[club.slug])
    assert (agent in links) == (who != "player")
    for href in links:
        r = c.get(href, follow=True)
        assert r.status_code == 200, href
        text = r.content.decode()
        for msg in NOT_FOR_YOU:
            assert msg not in text, href
        assert "wm-empty" not in text or "lock" not in text.split("wm-empty")[1][:300], href


def test_site_admin_without_membership_no_message_tile(login, club, site_admin):
    body = login(site_admin).get(reverse("club_home", args=[club.slug])).content.decode()
    assert reverse("accounts:message_new", args=[club.slug]) not in tile_hrefs(body)


@pytest.mark.parametrize(
    "who,sees",
    [("player", False), ("game_master", False), ("club_admin", True), ("site_admin", True)],
)
def test_people_email_column(who, sees, request, login, club, player):
    user = request.getfixturevalue(who)
    body = login(user).get(reverse("accounts:index", args=[club.slug])).content.decode()
    assert ("<th>Email</th>" in body) == sees
    assert ("player@example.com" in body) == sees
    assert ("Actions" in body) == sees


@pytest.mark.parametrize("who", ["player", "game_master"])
def test_xp_table_read_only(who, request, login, club):
    XPLevel.objects.get_or_create(club=club, band=1, defaults={"discover_xp": 1, "explore_xp": 2})
    user = request.getfixturevalue(who)
    c = login(user)
    url = reverse("map:xp", args=[club.slug])
    r = c.get(url)
    assert r.status_code == 200
    assert "<input" not in r.content.decode().split("<main")[-1].replace('type="hidden"', "")
    assert c.post(url, {"discover_1": 9, "explore_1": 9}).status_code == 403
    assert XPLevel.objects.get(club=club, band=1).discover_xp == 1


def test_xp_table_admin_edits(login, club, club_admin):
    XPLevel.objects.get_or_create(club=club, band=1)
    c = login(club_admin)
    url = reverse("map:xp", args=[club.slug])
    assert "discover_1" in c.get(url).content.decode()
