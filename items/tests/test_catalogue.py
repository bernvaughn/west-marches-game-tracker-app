import re

import pytest
from django.urls import reverse

from items.models import Item
from items.services import item_is_referenced
from ledger.services import Line, record

pytestmark = [pytest.mark.story("I1"), pytest.mark.django_db]

VALUE = {"value_pp": "", "value_gp": "", "value_sp": "", "value_cp": ""}


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def form(**kw):
    return {"name": "Lantern", "description": "", "traits": "", "details": "", **VALUE, **kw}


@pytest.fixture
def retired(club):
    return Item.objects.create(club=club, name="Old", retired=True)


@pytest.fixture
def other_item(other_club):
    return Item.objects.create(club=other_club, name="Foreign")


def test_members_see_active_catalogue(login, player, game_master, club, item, retired):
    for u in (player, game_master):
        c = login(u)
        r = c.get(url("index", club))
        assert r.status_code == 200
        assert b"Rope" in r.content and b"Old" not in r.content
        assert b"New item" not in r.content
        assert c.get(url("detail", club, item.pk)).status_code == 200
        assert c.get(url("detail", club, retired.pk)).status_code == 404
        assert c.get(url("index", club) + "?retired=1").content.count(b"Old") == 0


def test_value_uses_coins_filter(login, player, club):
    Item.objects.create(club=club, name="Gem", value_cp=1500)
    assert b"15 gp" in re.sub(rb"<[^>]+>", b"", login(player).get(url("index", club)).content)


@pytest.mark.parametrize("who", ["player", "game_master"])
def test_non_admins_get_403(request, login, club, item, who):
    c = login(request.getfixturevalue(who))
    assert c.get(url("create", club)).status_code == 403
    assert c.post(url("create", club), form()).status_code == 403
    assert c.get(url("edit", club, item.pk)).status_code == 403
    for name in ("edit", "retire", "restore", "delete"):
        assert c.post(url(name, club, item.pk), form(name="X")).status_code == 403
    item.refresh_from_db()
    assert item.name == "Rope" and not item.retired
    assert Item.objects.count() == 1


@pytest.mark.parametrize("who", ["club_admin", "site_admin"])
def test_admin_lifecycle(request, login, club, who):
    c = login(request.getfixturevalue(who))
    r = c.post(url("create", club), form(value_gp="1", value_sp="5", value_cp="3"))
    assert r.status_code == 302
    i = Item.objects.get(name="Lantern")
    assert i.club == club and i.value_cp == 153
    c.post(url("edit", club, i.pk), form(name="Lamp", value_pp="2"))
    i.refresh_from_db()
    assert (i.name, i.value_cp) == ("Lamp", 2000)
    c.post(url("retire", club, i.pk))
    i.refresh_from_db()
    assert i.retired
    assert b"Old" not in c.get(url("index", club)).content
    assert b"Lamp" in c.get(url("index", club) + "?retired=1").content
    c.post(url("restore", club, i.pk))
    i.refresh_from_db()
    assert not i.retired


def test_admin_sees_retired_detail(login, club_admin, club, retired):
    assert login(club_admin).get(url("detail", club, retired.pk)).status_code == 200


def test_duplicate_name_rules(login, club_admin, club, other_club, item):
    c = login(club_admin)
    r = c.post(url("create", club), form(name="rope"))
    assert r.status_code == 200 and "already exists" in r.content.decode()
    assert Item.objects.filter(club=club).count() == 1
    Item.objects.create(club=other_club, name="Lantern")
    assert c.post(url("create", club), form()).status_code == 302
    assert c.post(url("edit", club, item.pk), form(name="Rope")).status_code == 302


def test_cross_club_isolation(login, club_admin, player, club, other_club, other_item):
    c = login(club_admin)
    assert b"Foreign" not in c.get(url("index", club)).content
    pk = other_item.pk
    assert c.get(url("detail", club, pk)).status_code == 404
    assert c.get(url("edit", club, pk)).status_code == 404
    for n in ("retire", "restore", "delete"):
        assert c.post(url(n, club, pk)).status_code == 404
    assert login(player).get(url("detail", other_club, pk)).status_code == 404
    other_item.refresh_from_db()
    assert not other_item.retired


def test_unused_item_is_deleted(login, club_admin, club, item):
    r = login(club_admin).post(url("delete", club, item.pk))
    assert r.status_code == 302
    assert not Item.objects.filter(pk=item.pk).exists()


def test_used_item_is_retired_not_deleted(login, club_admin, club, item, character):
    record(character, "award", [Line(item=item, quantity=1)])
    c = login(club_admin)
    r = c.post(url("delete", club, item.pk), follow=True)
    item.refresh_from_db()
    assert item.retired
    assert "retired instead" in r.content.decode()


def test_item_is_referenced_other_models(club, item, character, club_admin):
    from agent_access.models import AgentConnection, ProposedBatch, ProposedLine
    from shops.models import Shop, ShopStock

    assert not item_is_referenced(item)
    shop = Shop.objects.create(club=club, name="S")
    ShopStock.objects.create(shop=shop, item=item)
    assert item_is_referenced(item)
    ShopStock.objects.all().delete()
    assert not item_is_referenced(item)
    conn = AgentConnection.objects.create(user=club_admin, club=club)
    batch = ProposedBatch.objects.create(
        club=club, connection=conn, user=club_admin, date="2026-01-01", idempotency_key="k"
    )
    ProposedLine.objects.create(batch=batch, character=character, item=item, quantity=1)
    assert item_is_referenced(item)
