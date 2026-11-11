from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from quests.models import Quest

D = date(2026, 6, 15)
ONE = timedelta(days=1)


@pytest.mark.story("Q2")
@pytest.mark.parametrize(
    "start,end,expected",
    [
        (D, None, "live"),
        (None, D, "live"),
        (D + ONE, None, "upcoming"),
        (None, D - ONE, "ended"),
        (None, None, "live"),
        (D - ONE, D + ONE, "live"),
        (D, D, "live"),
        (D - 10 * ONE, D - ONE, "ended"),
    ],
)
def test_status_edges(club, start, end, expected):
    q = Quest.objects.create(club=club, name="Q", start_date=start, end_date=end)
    assert q.status_on(D) == expected
    assert q.is_live_on(D) == (expected == "live")
    assert Quest.objects.live_on(D).filter(pk=q.pk).exists() == (expected == "live")


@pytest.mark.story("Q4")
def test_live_on_is_club_scoped(club, quest, upcoming_quest, ended_quest, other_club_quest):
    live = Quest.objects.for_club(club).live_on(timezone.localdate())
    assert list(live) == [quest]


@pytest.mark.story("Q4")
def test_index_hides_other_club(login, player, quest, other_club_quest):
    r = login(player).get(reverse("quests:index", args=["club-a"]))
    assert r.status_code == 200
    assert other_club_quest.name.encode() not in r.content


def _url(name, *args):
    return reverse(f"quests:{name}", args=["club-a", *args])


@pytest.mark.story("Q4")
def test_player_access(login, player, quest):
    c = login(player)
    assert c.get(_url("index")).status_code == 200
    assert c.get(_url("detail", quest.pk)).status_code == 200
    assert c.get(_url("turn_in", quest.pk)).status_code == 405
    assert c.post(_url("turn_in", quest.pk)).status_code == 302
    for name, args in [("manage", []), ("create", []), ("edit", [quest.pk])]:
        assert c.get(_url(name, *args)).status_code == 403
    assert c.post(_url("delete", quest.pk)).status_code == 403
    assert Quest.objects.filter(pk=quest.pk).exists()


@pytest.mark.story("Q4")
@pytest.mark.parametrize("who", ["club_admin", "site_admin"])
def test_admin_access(login, request, who, quest):
    c = login(request.getfixturevalue(who))
    for name, args in [("manage", []), ("create", []), ("edit", [quest.pk])]:
        assert c.get(_url(name, *args)).status_code == 200
    assert c.get(_url("delete", quest.pk)).status_code == 405
    assert c.post(_url("delete", quest.pk)).status_code == 302
    assert Quest.objects.filter(pk=quest.pk).exists()


@pytest.mark.story("Q4")
def test_other_club_quest_404(login, club_admin, other_club_quest):
    c = login(club_admin)
    pk = other_club_quest.pk
    assert c.get(_url("detail", pk)).status_code == 404
    assert c.post(_url("turn_in", pk)).status_code == 404
    assert c.get(_url("edit", pk)).status_code == 404
    assert c.post(_url("delete", pk)).status_code == 404


@pytest.mark.story("Q4")
def test_nav_manage_link(login, club_admin, site_admin, player, club):
    page = reverse("items:index", args=["club-a"])
    assert b"Manage quests" in login(club_admin).get(page).content
    assert b"Manage quests" in login(site_admin).get(page).content
    assert b"Manage quests" not in login(player).get(page).content


@pytest.mark.story("Q4")
def test_nav_without_club(login, player):
    assert login(player).get("/").status_code in (200, 302)
