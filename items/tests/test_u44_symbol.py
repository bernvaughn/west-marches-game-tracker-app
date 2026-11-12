import pytest
from django.urls import reverse

from items.models import Item

pytestmark = [pytest.mark.story("U44"), pytest.mark.django_db]

SPAN = '<span class="wm-item-symbol" aria-hidden="true">🪢</span> Rope'
VALUE = {"value_pp": "", "value_gp": "", "value_sp": "", "value_cp": ""}


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def data(**kw):
    return {"name": "Lantern", "description": "", "traits": "", "details": "", **VALUE, **kw}


def test_admin_sets_symbol_on_create_and_edit(login, club_admin, club):
    c = login(club_admin)
    assert c.post(url("create", club), data(symbol="🏮")).status_code == 302
    lantern = Item.objects.get(club=club, name="Lantern")
    assert lantern.symbol == "🏮"
    assert c.post(url("edit", club, lantern.pk), data(symbol="💡")).status_code == 302
    lantern.refresh_from_db()
    assert lantern.symbol == "💡"
    c.post(url("edit", club, lantern.pk), data(symbol=""))
    lantern.refresh_from_db()
    assert lantern.symbol == ""


def test_symbol_too_long_refused(login, club_admin, club):
    r = login(club_admin).post(url("create", club), data(symbol="123456789"))
    assert r.status_code == 200
    assert not Item.objects.filter(name="Lantern").exists()


def test_player_cannot_edit(login, player, club, item):
    assert login(player).get(url("edit", club, item.pk)).status_code == 403


def test_symbol_in_catalogue_and_detail(login, player, club, item):
    item.symbol = "🪢"
    item.save()
    c = login(player)
    assert SPAN in c.get(url("index", club)).content.decode()
    assert "🪢" in c.get(url("detail", club, item.pk)).content.decode()


def test_no_span_when_blank(login, player, club, item):
    assert "wm-item-symbol" not in login(player).get(url("index", club)).content.decode()


def test_cross_club_symbol_not_in_catalogue(login, player, club, other_club):
    Item.objects.create(club=other_club, name="Foreign", symbol="🦊")
    body = login(player).get(url("index", club)).content.decode()
    assert "🦊" not in body and "Foreign" not in body
