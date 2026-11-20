"""Tests for the stacked item form (story U123)."""

import pytest
from django.urls import reverse

from items.models import Item
from items.services import item_is_referenced
from ledger.models import LedgerLine
from ledger.services import Line, record
from player_characters.models import JunkMark
from shops.models import Shop, ShopStock

pytestmark = [pytest.mark.story("U123"), pytest.mark.django_db]


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def form(**kw):
    return {
        "name": "Lantern",
        "symbol": "",
        "description": "",
        "traits": "",
        "details": "",
        "gm_details": "",
        "rarity": "",
        "magic_type": "",
        "value_pp": "",
        "value_gp": "",
        "value_sp": "",
        "value_cp": "",
        "is_stacked": "",
        "unit_name": "",
        "value_units": "",
        **kw,
    }


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_stacked_fields_on_create_page(login, club_admin, club):
    c = login(club_admin)
    r = c.get(url("create", club))
    assert r.status_code == 200
    assert b"Stacked item" in r.content
    assert b"Unit name" in r.content
    assert b"Units the value covers" in r.content


def test_club_admin_can_create_stacked_item(login, club_admin, club):
    c = login(club_admin)
    r = c.post(
        url("create", club),
        form(
            name="Parchment",
            value_cp="100",
            is_stacked="on",
            unit_name="sheet",
            value_units="10",
        ),
    )
    assert r.status_code == 302
    item = Item.objects.get(name="Parchment")
    assert item.club == club
    assert item.is_stacked is True
    assert item.unit_name == "sheet"
    assert item.value_units == 10
    assert item.value_cp == 100


def test_create_stacked_item_rejected_without_unit_name(login, club_admin, club):
    c = login(club_admin)
    r = c.post(
        url("create", club),
        form(name="Parchment", value_cp="100", is_stacked="on", value_units="10"),
    )
    assert r.status_code == 200
    assert "A stacked item needs a unit name." in r.content.decode()
    assert not Item.objects.filter(name="Parchment").exists()


def test_create_stacked_item_is_not_a_container(login, club_admin, club):
    c = login(club_admin)
    c.post(
        url("create", club),
        form(
            name="Parchment", value_cp="100", is_stacked="on", unit_name="sheet", value_units="10"
        ),
    )
    assert Item.objects.get(name="Parchment").is_container is False


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


def test_container_cannot_be_stacked_on_edit(login, club_admin, club):
    c = login(club_admin)
    container = Item.objects.create(club=club, name="Chest", is_container=True)
    r = c.post(
        url("edit", club, container.pk),
        form(name="Chest", is_container="on", is_stacked="on", unit_name="slot"),
    )
    assert r.status_code == 200
    assert "An item is a container or stacked, never both." in r.content.decode()
    container.refresh_from_db()
    assert not container.is_stacked


def test_stacked_item_cannot_become_container_on_edit(login, club_admin, club):
    c = login(club_admin)
    stacked = Item.objects.create(
        club=club, name="Parchment", is_stacked=True, unit_name="sheet", value_units=10
    )
    r = c.post(
        url("edit", club, stacked.pk),
        form(name="Parchment", is_stacked="on", unit_name="sheet", is_container="on"),
    )
    assert r.status_code == 200
    assert "An item is a container or stacked, never both." in r.content.decode()
    stacked.refresh_from_db()
    assert not stacked.is_container


def test_value_and_units_edit_only_saves_item(login, club_admin, club, character):
    c = login(club_admin)
    item = Item.objects.create(
        club=club, name="Rope", is_stacked=True, unit_name="ft", value_units=50, value_cp=100
    )
    record(character, "award", [Line(item=item, quantity=10)])
    shop = Shop.objects.create(club=club, name="General Store")
    ShopStock.objects.create(shop=shop, item=item, bundle_units=1, quantity=5, sell_percent=100)
    JunkMark.objects.create(character=character, item=item, quantity=3)

    lines_before = item.stock_entries.count()
    r = c.post(
        url("edit", club, item.pk),
        form(
            name=item.name,
            value_cp="150",
            value_units="20",
            is_stacked="on",
            unit_name="ft",
        ),
    )
    assert r.status_code == 302
    item.refresh_from_db()
    assert item.value_cp == 150
    assert item.value_units == 20
    assert item.unit_name == "ft"
    assert item.is_stacked is True
    assert item.stock_entries.count() == lines_before
    assert item.stock_entries.get().quantity == 5
    assert item.stock_entries.get().sell_percent == 100
    assert JunkMark.objects.get(character=character, item=item).quantity == 3
    assert LedgerLine.objects.filter(item=item).count() == 1


def test_non_stacked_save_resets_unit_and_units(login, club_admin, club):
    c = login(club_admin)
    item = Item.objects.create(club=club, name="Rope", value_cp=100)
    r = c.post(
        url("edit", club, item.pk),
        form(name="Rope", unit_name="ft", value_units="5"),
    )
    assert r.status_code == 302
    item.refresh_from_db()
    assert not item.is_stacked
    assert item.unit_name == ""
    assert item.value_units == 1


def test_edit_shows_stacked_fields(login, club_admin, club):
    item = Item.objects.create(
        club=club, name="Rope", is_stacked=True, unit_name="ft", value_units=50
    )
    c = login(club_admin)
    r = c.get(url("edit", club, item.pk))
    assert r.status_code == 200
    assert b'id="id_is_stacked"' in r.content
    assert b"ft" in r.content


# ---------------------------------------------------------------------------
# Referenced item: flip refused, link to convert page
# ---------------------------------------------------------------------------


def test_flip_stacked_on_referenced_item_refused_with_convert_link(
    login, club_admin, club, character, item
):
    c = login(club_admin)
    record(character, "award", [Line(item=item, quantity=2)])
    assert item_is_referenced(item)
    convert_url = url("convert", club, item.pk)
    r = c.post(
        url("edit", club, item.pk),
        form(name=item.name, is_stacked="on", unit_name="ft", value_units="1"),
    )
    assert r.status_code == 200
    assert convert_url in r.content.decode()
    assert "Convert to stacked" in r.content.decode()
    item.refresh_from_db()
    assert not item.is_stacked


def test_unreferenced_item_can_be_stacked_and_unstacked(login, club_admin, club):
    c = login(club_admin)
    item = Item.objects.create(club=club, name="Rope", value_cp=100)
    assert not item_is_referenced(item)
    r = c.post(
        url("edit", club, item.pk),
        form(name="Rope", is_stacked="on", unit_name="ft", value_units="50"),
    )
    assert r.status_code == 302
    item.refresh_from_db()
    assert item.is_stacked and item.unit_name == "ft" and item.value_units == 50

    r = c.post(url("edit", club, item.pk), form(name="Rope"))
    assert r.status_code == 302
    item.refresh_from_db()
    assert not item.is_stacked
    assert item.unit_name == ""
    assert item.value_units == 1


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["player", "game_master"])
def test_non_admins_cannot_create_or_edit_stacked(request, login, club, who, item):
    c = login(request.getfixturevalue(who))
    assert c.post(url("create", club), form(is_stacked="on", unit_name="ft")).status_code == 403
    assert c.get(url("edit", club, item.pk)).status_code == 403
    assert c.post(url("edit", club, item.pk), form(is_stacked="on")).status_code == 403
    item.refresh_from_db()
    assert not item.is_stacked


def test_anonymous_redirected(client, club, item):
    assert client.get(url("create", club)).status_code == 302
    assert client.post(url("create", club), form()).status_code == 302
    assert client.get(url("edit", club, item.pk)).status_code == 302


def test_other_club_admin_404(login, club_admin, other_club, club, item):
    c = login(club_admin)
    assert c.get(url("edit", other_club, item.pk)).status_code == 404
    assert c.post(url("edit", other_club, item.pk), form()).status_code == 404
    assert c.get(url("create", other_club)).status_code == 404
    item.refresh_from_db()
    assert not item.is_stacked
