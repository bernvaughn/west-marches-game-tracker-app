import datetime

import pytest
from django.urls import reverse

from accounts.models import Membership, Message
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import coin_balance, item_quantities
from map import services as map_services
from map.models import CreditGrant, FoundMark, HexMap, Location, Tile, TileVisit
from player_characters.models import Character

pytestmark = pytest.mark.story("U30")

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def msg(club, player, character):
    return Message.objects.create(
        club=club,
        sender=Membership.objects.get(user=player, club=club),
        character=character,
        body="Please grant",
    )


@pytest.fixture
def hex_map(club):
    return HexMap.objects.create(club=club, name="Wilds")


@pytest.fixture
def location(hex_map):
    tile, _ = Tile.objects.get_or_create(map=hex_map, q=2, r=1)
    return Location.objects.create(tile=tile, name="Old Keep")


def url(club, msg):
    return reverse("accounts:message_grant", args=[club.slug, msg.pk])


def payload(character, **extra):
    data = {
        "character": character.pk,
        "note": "From message",
        "date": "2026-01-02",
        "items-TOTAL_FORMS": 3,
        "items-INITIAL_FORMS": 0,
        "items-MIN_NUM_FORMS": 0,
        "items-MAX_NUM_FORMS": 3,
    }
    data.update(extra)
    return data


def test_coins_grant(club, club_admin, character, msg, login):
    r = login(club_admin).post(url(club, msg), payload(character, coins_gp=5, mark_handled="on"))
    assert r.status_code == 302
    e = LedgerEntry.objects.get()
    assert (e.kind, e.note, e.date, e.created_by, e.source_message) == (
        "award",
        "From message",
        datetime.date(2026, 1, 2),
        club_admin,
        msg,
    )
    assert coin_balance(character) == 500
    msg.refresh_from_db()
    assert msg.status == "handled"


def test_items_grant(club, club_admin, character, msg, item, login):
    other = Item.objects.create(club=club, name="Lamp", value_cp=5)
    data = payload(
        character,
        **{
            "items-0-item": item.pk,
            "items-0-quantity": 2,
            "items-1-item": other.pk,
            "items-1-quantity": 1,
        },
    )
    assert login(club_admin).post(url(club, msg), data).status_code == 302
    assert LedgerEntry.objects.count() == 1
    assert item_quantities(character) == {item.pk: 2, other.pk: 1}


def test_unchecked_stays_open(club, club_admin, character, msg, login):
    login(club_admin).post(url(club, msg), payload(character, coins_cp=1))
    msg.refresh_from_db()
    assert msg.status == "open"


def test_nothing_to_grant_errors(club, club_admin, character, msg, login):
    r = login(club_admin).post(url(club, msg), payload(character))
    assert r.status_code == 200
    assert "Enter something to grant" in r.content.decode()
    assert not LedgerEntry.objects.exists()


def test_visit_by_location_and_tile(club, club_admin, character, msg, location, hex_map, login):
    c = login(club_admin)
    c.post(url(club, msg), payload(character, map_kind="visit", location=location.pk))
    v = TileVisit.objects.get()
    assert (v.q, v.r, v.source_message, v.date) == (2, 1, msg, datetime.date(2026, 1, 2))
    c.post(url(club, msg), payload(character, map_kind="visit", hex_map=hex_map.pk, q=5, r=5))
    assert TileVisit.objects.filter(q=5, r=5, source_message=msg).exists()


@pytest.mark.parametrize("kind", ["discovered", "explored"])
def test_credit(club, club_admin, character, msg, location, login, kind):
    login(club_admin).post(url(club, msg), payload(character, map_kind=kind, location=location.pk))
    g = CreditGrant.objects.get()
    assert (g.character, g.source_message, g.credit.kind) == (character, msg, kind)
    assert TileVisit.objects.get().source_message == msg


def test_found(club, club_admin, character, msg, location, login):
    login(club_admin).post(
        url(club, msg), payload(character, map_kind="found", location=location.pk)
    )
    f = FoundMark.objects.get()
    assert f.source_message == msg and f.date == datetime.date(2026, 1, 2)


def test_location_required(club, club_admin, character, msg, login):
    r = login(club_admin).post(url(club, msg), payload(character, map_kind="found"))
    assert r.status_code == 200 and not FoundMark.objects.exists()


def test_defaults_on_get(club, club_admin, character, msg, login):
    r = login(club_admin).get(url(club, msg))
    form = r.context["form"]
    assert form["note"].value() == f"From message #{msg.pk}"
    assert form["date"].value() is not None
    assert form["character"].value() == character.pk
    assert form["mark_handled"].value() is True


def test_inbox_lists_granted(club, club_admin, character, msg, location, login):
    c = login(club_admin)
    c.post(url(club, msg), payload(character, coins_gp=3, map_kind="found", location=location.pk))
    page = c.get(
        reverse("accounts:message_inbox", args=[club.slug]) + "?status=all"
    ).content.decode()
    assert "Granted" in page and "Found: Old Keep" in page and "gp" in page
    assert "Grant</a>" in page


def test_permissions(club, club_admin, game_master, player, other_club, club_b_admin, msg, login):
    u = url(club, msg)
    for user in (game_master, player):
        assert login(user).get(u).status_code == 403
        assert login(user).post(u, {}).status_code == 403
    assert login(club_admin).get(u).status_code == 200
    bu = reverse("accounts:message_grant", args=[other_club.slug, msg.pk])
    assert login(club_b_admin).get(bu).status_code == 404


def test_cross_club_refused(club, club_admin, other_club, character, msg, login):
    b_item = Item.objects.create(club=other_club, name="Foreign", value_cp=1)
    b_map = HexMap.objects.create(club=other_club, name="BMap")
    b_loc = Location.objects.create(tile=Tile.objects.get(map=b_map, q=0, r=0), name="BLoc")
    b_char = Character.objects.create(
        club=other_club,
        owner=Membership.objects.create(
            user=club_admin.__class__.objects.create_user("x@e.com", "pw", display_name="X"),
            club=other_club,
        ),
        name="BChar",
    )
    c = login(club_admin)
    cases = [
        payload(b_char, coins_2=1),
        payload(character, **{"items-0-item": b_item.pk, "items-0-quantity": 1}),
        payload(character, map_kind="found", location=b_loc.pk),
        payload(character, map_kind="visit", hex_map=b_map.pk, q=1, r=1),
    ]
    for data in cases:
        assert c.post(url(club, msg), data).status_code == 200
    assert not LedgerEntry.objects.exists()
    assert not FoundMark.objects.exists()
    assert not TileVisit.objects.exists()


def test_htmx_responses(club, club_admin, character, msg, login):
    c = login(club_admin)
    frag = c.get(url(club, msg), **HX).content.decode()
    assert "<html" not in frag and "Grant for message" in frag
    assert "<html" in c.get(url(club, msg)).content.decode()
    r = c.post(url(club, msg), payload(character, coins_cp=1), **HX)
    assert r.status_code == 204 and "appModalClose" in r["HX-Trigger"]


def test_change_character(club, club_admin, other_player, msg, login):
    other = Character.objects.create(
        club=club, owner=Membership.objects.get(user=other_player, club=club), name="Bob"
    )
    login(club_admin).post(url(club, msg), payload(other, coins_cp=2))
    assert LedgerEntry.objects.get().character == other


def test_ledger_error_rolls_back(club, club_admin, character, msg, location, login, monkeypatch):
    from accounts.views import inbox
    from ledger.services import LedgerError

    def boom(*a, **k):
        raise LedgerError("nope")

    monkeypatch.setattr(inbox.map_services, "add_found_marks", boom)
    r = login(club_admin).post(
        url(club, msg),
        payload(character, coins_cp=2, map_kind="found", location=location.pk, mark_handled="on"),
    )
    assert r.status_code == 200 and "nope" in r.content.decode()
    assert not LedgerEntry.objects.exists()
    msg.refresh_from_db()
    assert msg.status == "open"


def test_service_source_message(location, character, msg):
    created = map_services.add_found_marks(location, [character], source_message=msg)
    assert created[0].source_message == msg
    assert map_services.add_found_marks(location, [character], source_message=msg) == []
    map_services.add_to_credit(location, "explored", [character], source_message=msg)
    map_services.add_to_credit(location, "explored", [character], source_message=msg)
    assert CreditGrant.objects.count() == 1
    assert TileVisit.objects.get().source_message == msg


def test_inbox_list_does_not_leak_htmx_attrs(club, club_admin, msg, login):
    page = (
        login(club_admin).get(reverse("accounts:message_inbox", args=[club.slug])).content.decode()
    )
    start = page.index('id="inbox-list"')
    tag = page[start : page.index(">", start)]
    assert 'hx-select="#inbox-list"' in tag and 'hx-disinherit="*"' in tag
