import re

import pytest
from django.urls import reverse

from items import rarity
from items.models import Item

pytestmark = [pytest.mark.story("U83"), pytest.mark.django_db]

BANDS = {
    "trivial": ("1–9 cp", "a loaf of bread"),
    "cheap": ("1–9 sp", "a waterskin"),
    "standard": ("1–10 gp", "a shovel"),
    "fine": ("11–100 gp", "a riding horse"),
    "luxury": ("101–1,000 gp", "a small boat"),
    "exotic": ("1,001 gp and up", "a warship"),
}


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def mk(club, name, cp, band=""):
    return Item.objects.create(club=club, name=name, value_cp=cp, rarity=band)


def names(resp):
    return re.findall(r"<td>(?:<span[^>]*>[^<]*</span> )?([^<]+)</td><td>", resp.content.decode())


def test_three_groups_on_page_and_modal(login, club_admin, club):
    c = login(club_admin)
    for body in (
        c.get(url("create", club)).content.decode(),
        c.get(url("create", club), HTTP_HX_REQUEST="true").content.decode(),
    ):
        for label in ("Magic items", "Everyday goods", "Special"):
            assert f'<optgroup label="{label}">' in body
        for key in [*BANDS, "special", "common"]:
            assert f'value="{key}"' in body


@pytest.mark.parametrize("key,expected", BANDS.items())
def test_range_and_examples(key, expected, login, club_admin, club):
    assert rarity.range_label(key) == expected[0]
    assert expected[1] in rarity.examples(key)
    body = login(club_admin).get(url("create", club)).content.decode()
    assert expected[0] in body and expected[1] in body


def test_special_has_no_range(login, club_admin, club):
    assert rarity.range_label("special") == "" and rarity.examples("special") == ""
    assert "special" not in [r[0] for r in rarity.ranges()]
    body = login(club_admin).get(url("create", club)).content.decode()
    assert "No suggested range." in body


def test_special_saves(login, club_admin, club):
    data = {"name": "Odd", "description": "", "traits": "", "details": "", "rarity": "special"}
    assert login(club_admin).post(url("create", club), data).status_code == 302
    assert Item.objects.get(name="Odd").rarity == "special"


def test_panel_present(login, club_admin, club):
    c = login(club_admin)
    for body in (
        c.get(url("create", club)).content.decode(),
        c.get(url("create", club), HTTP_HX_REQUEST="true").content.decode(),
    ):
        assert f'hx-get="{url("references", club)}"' in body
        assert "delay:300ms" in body and 'name="ref_q"' in body


def test_same_band_then_nearest(login, club_admin, club):
    mk(club, "FarFine", 9000, "fine")
    mk(club, "NearOther", 1100, "standard")
    mk(club, "FarOther", 50000, "rare")
    mk(club, "NearFine", 1200, "fine")
    r = login(club_admin).get(url("references", club), {"rarity": "fine", "value_gp": "11"})
    assert names(r) == ["NearFine", "FarFine", "NearOther", "FarOther"]


def test_nearest_only_without_band(login, club_admin, club):
    mk(club, "A", 100)
    mk(club, "B", 5000)
    r = login(club_admin).get(url("references", club), {"value_gp": "49"})
    assert names(r) == ["B", "A"]


def test_limit_ten_and_empty(login, club_admin, club):
    for i in range(15):
        mk(club, f"I{i:02}", i, "trivial")
    c = login(club_admin)
    assert len(names(c.get(url("references", club), {"rarity": "trivial"}))) == 10
    assert names(c.get(url("references", club))) == []


def test_excludes_retired_and_current(login, club_admin, club):
    cur = mk(club, "Cur", 100, "standard")
    mk(club, "Old", 100, "standard").__class__.objects.filter(name="Old").update(retired=True)
    mk(club, "Keep", 100, "standard")
    r = login(club_admin).get(url("references", club), {"rarity": "standard", "exclude": cur.pk})
    assert names(r) == ["Keep"]


def test_search(login, club_admin, club):
    mk(club, "Bread", 1, "trivial")
    mk(club, "Torch", 1, "trivial")
    r = login(club_admin).get(url("references", club), {"ref_q": "brea", "rarity": "trivial"})
    assert names(r) == ["Bread"]


def test_cross_club_isolation(login, club_admin, club, other_club):
    mk(other_club, "Foreign", 100, "standard")
    mk(club, "Mine", 100, "standard")
    c = login(club_admin)
    body = c.get(url("references", club), {"rarity": "standard"}).content.decode()
    assert "Mine" in body and "Foreign" not in body
    assert "Foreign" not in c.get(url("references", club), {"ref_q": "For"}).content.decode()


def test_player_refused(login, player, club):
    assert login(player).get(url("references", club)).status_code in (302, 403, 404)
