import json

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from items.models import Item

pytestmark = pytest.mark.story("S3")
HX = {"HTTP_HX_REQUEST": "true"}


def _create(club):
    return reverse("items:create", args=[club.slug])


def _stock_add(club, shop):
    return reverse("shops:stock_add", args=[club.slug, shop.pk])


def test_modal_get_returns_fragment(club, club_admin, login):
    r = login(club_admin).get(_create(club), **HX)
    html = r.content.decode()
    assert "modal-header" in html and "hx-post" in html and 'name="symbol"' in html
    assert "<html" not in html


def test_modal_post_creates_and_triggers(club, club_admin, login):
    r = login(club_admin).post(_create(club), {"name": "Lamp"}, **HX)
    assert r.status_code == 204
    assert "HX-Redirect" not in r and "HX-Refresh" not in r
    item = Item.objects.get(name="Lamp")
    assert item.club == club
    trig = json.loads(r["HX-Trigger"])
    assert trig["appModalClose"] is True
    assert trig["itemCreated"] == {"id": item.pk, "name": "Lamp"}


def test_modal_duplicate_name_shows_error(club, club_admin, item, login):
    r = login(club_admin).post(_create(club), {"name": item.name}, **HX)
    assert r.status_code == 200
    assert "already exists" in r.content.decode()
    assert Item.objects.filter(club=club).count() == 1


def test_stock_form_has_link_and_script(club, club_admin, shop, stock, login):
    c = login(club_admin)
    html = c.get(_stock_add(club, shop)).content.decode()
    assert f'hx-get="{_create(club)}"' in html
    assert "next=" in html and "stock_new_item.js" in html
    edit = reverse("shops:stock_edit", args=[club.slug, shop.pk, stock.pk])
    assert _create(club) not in c.get(edit).content.decode()
    src = open(finders.find("js/stock_new_item.js")).read()
    assert "itemCreated" in src


def test_other_stock_fields_kept_and_stock_add_works(club, club_admin, shop, login):
    c = login(club_admin)
    c.post(_create(club), {"name": "Lamp"}, **HX)
    item = Item.objects.get(name="Lamp")
    r = c.post(_stock_add(club, shop), {"item": item.pk, "quantity": 3})
    assert r.status_code == 302
    assert shop.stock.get(item=item).quantity == 3


def test_no_js_returns_with_item_preselected(club, club_admin, shop, login):
    c = login(club_admin)
    back = _stock_add(club, shop)
    r = c.post(f"{_create(club)}?next={back}", {"name": "Lamp"})
    item = Item.objects.get(name="Lamp")
    assert r.status_code == 302 and r.url == f"{back}?item={item.pk}"
    html = c.get(r.url).content.decode()
    assert f'value="{item.pk}" selected' in html


def test_no_js_get_has_hidden_next(club, club_admin, shop, login):
    back = _stock_add(club, shop)
    html = login(club_admin).get(f"{_create(club)}?next={back}").content.decode()
    assert 'name="next"' in html


@pytest.mark.parametrize("bad", ["https://evil.example/x", "//evil.example"])
def test_foreign_next_ignored(club, club_admin, login, bad):
    r = login(club_admin).post(f"{_create(club)}?next={bad}", {"name": "Lamp"})
    item = Item.objects.get(name="Lamp")
    assert r.url == reverse("items:detail", args=[club.slug, item.pk])


def test_player_forbidden(club, player, login):
    c = login(player)
    assert c.get(_create(club), **HX).status_code == 403
    assert c.post(_create(club), {"name": "Lamp"}).status_code == 403
    assert c.post(_create(club), {"name": "Lamp"}, **HX).status_code == 403
    assert not Item.objects.filter(name="Lamp").exists()


@pytest.mark.parametrize("which", ["other", "stocked", "junk"])
def test_preselect_ignores_bad_ids(club, other_club, club_admin, shop, stock, login, which):
    other = Item.objects.create(club=other_club, name="Foreign")
    value = {"other": other.pk, "stocked": stock.item.pk, "junk": "abc"}[which]
    html = login(club_admin).get(f"{_stock_add(club, shop)}?item={value}").content.decode()
    assert "selected" not in html.replace('value="" selected', "")
    assert "Foreign" not in html
