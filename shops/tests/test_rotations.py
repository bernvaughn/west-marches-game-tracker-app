from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from shops.models import Rotation, Shop, ShopStock
from shops.services import is_open, open_shops

pytestmark = pytest.mark.django_db


def url(name, club, *args):
    return reverse(f"shops:{name}", args=[club.slug, *args])


def payload(name="R", open_date="2030-01-01", close_date="", shops=()):
    return {
        "name": name,
        "open_date": open_date,
        "close_date": close_date,
        "shops": [s.pk for s in shops],
    }


def make(club, shop, open_date, close_date=None, name="R"):
    r = Rotation.objects.create(club=club, name=name, open_date=open_date, close_date=close_date)
    r.shops.add(shop)
    return r


@pytest.mark.story("S2")
def test_admin_and_site_admin_create(club, club_admin, site_admin, shop, login):
    for user, name in ((club_admin, "A"), (site_admin, "B")):
        resp = login(user).post(
            url("rotation_create", club), payload(name, "2030-01-01", "2030-02-01", [shop])
        )
        assert resp.status_code == 302
        assert list(Rotation.objects.get(name=name).shops.all()) == [shop]


@pytest.mark.story("S2")
def test_shop_in_two_rotations(club, shop):
    make(club, shop, date(2030, 1, 1), date(2030, 2, 1), "Jan")
    make(club, shop, date(2030, 6, 1), date(2030, 7, 1), "Jun")
    assert is_open(shop, date(2030, 1, 15))
    assert is_open(shop, date(2030, 6, 15))
    assert not is_open(shop, date(2030, 4, 1))


@pytest.mark.story("S2")
def test_future_rotation(club, club_admin, shop, login):
    today = timezone.localdate()
    future = today + timedelta(days=30)
    resp = login(club_admin).post(
        url("rotation_create", club), payload("Soon", future.isoformat(), "", [shop])
    )
    assert resp.status_code == 302
    assert shop not in open_shops(club, today)
    assert shop in open_shops(club, future)


@pytest.mark.story("S2")
def test_stock_unchanged_on_edit_and_delete(club, club_admin, shop, stock, login):
    r = make(club, shop, date(2030, 1, 1))
    client = login(club_admin)
    resp = client.post(url("rotation_edit", club, r.pk), payload("R", "2030-01-01", "", []))
    assert resp.status_code == 302
    assert r.shops.count() == 0
    stock.refresh_from_db()
    assert stock.quantity == 2
    resp = client.post(url("rotation_delete", club, r.pk))
    assert resp.status_code == 302
    assert not Rotation.objects.filter(pk=r.pk).exists()
    assert Shop.objects.filter(pk=shop.pk).exists()
    assert ShopStock.objects.get(pk=stock.pk).quantity == 2


@pytest.mark.story("S2")
def test_list_shows_statuses(club, club_admin, shop, login):
    today = timezone.localdate()
    make(club, shop, today + timedelta(days=5), None, "Fut")
    make(club, shop, today - timedelta(days=5), today + timedelta(days=5), "Now")
    make(club, shop, today - timedelta(days=9), today - timedelta(days=5), "Old")
    make(club, shop, today - timedelta(days=9), None, "Forever")
    html = login(club_admin).get(url("rotation_list", club)).content.decode()
    for text in ("Fut", "Now", "Old", "Forever", "Lantern", "upcoming", "closed", "always open"):
        assert text in html
    assert "open</td>" in html


@pytest.mark.story("U4")
def test_edit_changes_open_shops(club, club_admin, shop, closed_shop, login):
    today = timezone.localdate()
    r = make(club, shop, date(2000, 1, 1))
    assert set(open_shops(club, today)) == {shop}
    login(club_admin).post(
        url("rotation_edit", club, r.pk), payload("R", "2000-01-01", "", [closed_shop])
    )
    assert set(open_shops(club, today)) == {closed_shop}


@pytest.mark.story("U5")
def test_no_close_date_stays_open(club, club_admin, shop, login):
    far = timezone.localdate() + timedelta(days=3650)
    resp = login(club_admin).post(
        url("rotation_create", club), payload("Always", "2000-01-01", "", [shop])
    )
    assert resp.status_code == 302
    assert Rotation.objects.get().close_date is None
    assert shop in open_shops(club, far)
    assert is_open(shop, far)
    html = login(club_admin).get(url("rotation_list", club)).content.decode()
    assert "always open" in html


@pytest.mark.story("S2")
def test_close_before_open_refused(club, club_admin, shop, login):
    resp = login(club_admin).post(
        url("rotation_create", club), payload("Bad", "2030-02-01", "2030-01-01", [shop])
    )
    assert resp.status_code == 200
    assert "on or after the open date" in resp.content.decode()
    assert not Rotation.objects.exists()


@pytest.mark.story("S2")
def test_other_club_shop_refused(club, club_admin, other_shop, login):
    resp = login(club_admin).post(
        url("rotation_create", club), payload("X", "2030-01-01", "", [other_shop])
    )
    assert resp.status_code == 200
    assert not Rotation.objects.exists()
    assert other_shop.rotations.count() == 0


@pytest.mark.story("S2")
def test_player_forbidden(club, player, shop, login):
    r = make(club, shop, date(2030, 1, 1))
    c = login(player)
    for name, args in (("rotation_list", ()), ("rotation_create", ()),
                       ("rotation_edit", (r.pk,)), ("rotation_delete", (r.pk,))):
        assert c.get(url(name, club, *args)).status_code in (403, 405), name
    for name, args in (("rotation_create", ()), ("rotation_edit", (r.pk,)),
                       ("rotation_delete", (r.pk,))):
        assert c.post(url(name, club, *args), payload()).status_code == 403, name
    assert Rotation.objects.filter(pk=r.pk).exists()
    assert c.get(url("rotation_list", club)).status_code == 403


@pytest.mark.story("S2")
def test_delete_get_not_allowed(club, club_admin, shop, login):
    r = make(club, shop, date(2030, 1, 1))
    assert login(club_admin).get(url("rotation_delete", club, r.pk)).status_code == 405


@pytest.mark.story("S2")
def test_cross_club_404(club, other_club, club_admin, other_shop, login):
    r = make(other_club, other_shop, date(2030, 1, 1))
    c = login(club_admin)
    assert c.get(url("rotation_edit", club, r.pk)).status_code == 404
    assert c.post(url("rotation_edit", club, r.pk), payload()).status_code == 404
    assert c.post(url("rotation_delete", club, r.pk)).status_code == 404
    assert Rotation.objects.filter(pk=r.pk).exists()
    html = c.get(url("rotation_list", club)).content.decode()
    assert "Elsewhere" not in html
