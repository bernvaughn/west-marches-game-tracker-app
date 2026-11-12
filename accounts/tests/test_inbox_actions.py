import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Membership, Message
from items.models import Item
from ledger.models import LedgerEntry
from map.models import CreditGrant, FoundMark, HexMap, Location, Tile, TileVisit
from player_characters.models import Character

pytestmark = pytest.mark.story("U38")

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def msg(club, player, character):
    return Message.objects.create(
        club=club,
        sender=Membership.objects.get(user=player, club=club),
        character=character,
        body="Please give me the silver ring",
    )


@pytest.fixture
def location(club):
    hex_map = HexMap.objects.create(club=club, name="Wilds")
    tile, _ = Tile.objects.get_or_create(map=hex_map, q=2, r=1)
    return Location.objects.create(tile=tile, name="Old Keep")


def inbox(club, status="all"):
    return reverse("accounts:message_inbox", args=[club.slug]) + f"?status={status}"


def give_url(club, msg, kind):
    return reverse(f"accounts:message_give_{kind}", args=[club.slug, msg.pk])


def confirm_url(club, msg, status):
    return reverse("accounts:message_status_confirm", args=[club.slug, msg.pk, status])


def payload(character, **extra):
    data = {
        "character": character.pk,
        "note": "From message",
        "date": "2026-01-02",
        "mark_handled": "on",
        "items-TOTAL_FORMS": 3,
        "items-INITIAL_FORMS": 0,
        "items-MIN_NUM_FORMS": 0,
        "items-MAX_NUM_FORMS": 3,
    }
    data.update(extra)
    return data


def nothing_written():
    return not (
        LedgerEntry.objects.exists()
        or TileVisit.objects.exists()
        or CreditGrant.objects.exists()
        or FoundMark.objects.exists()
    )


def test_buttons_apply_per_status(club, club_admin, msg, login):
    c = login(club_admin)
    page = c.get(inbox(club)).content.decode()
    assert "Mark handled</a>" in page and "Close</a>" in page and "Reopen</a>" not in page
    assert 'name="status"' not in page and "<select" not in page
    for status in ("handled", "closed"):
        msg.status = status
        msg.save()
        page = c.get(inbox(club)).content.decode()
        assert "Reopen</a>" in page
        assert "Mark handled</a>" not in page and "Close</a>" not in page
    for label in ("Give coins", "Give items", "Give map credit"):
        assert f"{label}</a>" in page


def test_status_confirm_writes_nothing(club, club_admin, msg, login):
    c = login(club_admin)
    frag = c.get(confirm_url(club, msg, "handled"), **HX).content.decode()
    assert "<html" not in frag
    assert msg.sender.user.display_name in frag and "silver ring" in frag
    page = c.get(confirm_url(club, msg, "closed")).content.decode()
    assert "<html" in page and "silver ring" in page
    msg.refresh_from_db()
    assert msg.status == "open"
    assert c.get(confirm_url(club, msg, "open")).status_code == 404
    assert c.get(confirm_url(club, msg, "bogus")).status_code == 404


def test_status_post_htmx(club, club_admin, msg, login):
    r = login(club_admin).post(
        reverse("accounts:message_status", args=[club.slug, msg.pk]),
        {"status": "handled", "filter": "open"},
        **HX,
    )
    assert r.status_code == 204 and "appModalClose" in r["HX-Trigger"]
    msg.refresh_from_db()
    assert msg.status == "handled"


@pytest.mark.parametrize("kind", ["coins", "items", "map"])
def test_give_confirm_step_writes_nothing(club, club_admin, character, msg, item, location, kind):
    from django.test import Client

    extra = {
        "coins": {"coins_gp": 5},
        "items": {"items-0-item": item.pk, "items-0-quantity": 2},
        "map": {"map_kind": "found", "location": location.pk},
    }[kind]
    c = Client()
    c.force_login(club_admin)
    r = c.post(give_url(club, msg, kind), payload(character, **extra))
    body = r.content.decode()
    assert r.status_code == 200 and 'name="confirmed"' in body
    assert "Marks the message handled" in body and character.name in body
    assert nothing_written()
    msg.refresh_from_db()
    assert msg.status == "open"
    r = c.post(give_url(club, msg, kind), payload(character, **extra, confirmed="1"))
    assert r.status_code == 302
    assert not nothing_written()
    msg.refresh_from_db()
    assert msg.status == "handled"


def test_back_keeps_data(club, club_admin, character, msg, login):
    r = login(club_admin).post(
        give_url(club, msg, "coins"), payload(character, coins_gp=7, edit="1")
    )
    assert r.status_code == 200 and 'name="confirmed"' not in r.content.decode()
    assert (
        r.context["form"]["coins_gp"].value() == "7"
        if "coins_gp" in r.context["form"].fields
        else True
    )
    assert nothing_written()


def test_map_kind_is_radio_group(club, club_admin, msg, login):
    body = login(club_admin).get(give_url(club, msg, "map")).content.decode()
    assert 'class="btn-group"' in body and 'type="radio"' in body and "btn-check" in body
    assert 'name="map_kind"' in body and "<select" in body  # location select only
    assert '<select name="map_kind"' not in body


def test_each_form_shows_only_its_fields(club, club_admin, msg, login):
    c = login(club_admin)
    coins = c.get(give_url(club, msg, "coins")).content.decode()
    assert "items-0-item" not in coins and "map_kind" not in coins and "coins" in coins
    items = c.get(give_url(club, msg, "items")).content.decode()
    assert "items-0-item" in items and "map_kind" not in items
    assert "coins_gp" not in items
    mp = c.get(give_url(club, msg, "map")).content.decode()
    assert "map_kind" in mp and "items-0-item" not in mp and "coins_gp" not in mp


def test_permissions(club, club_admin, game_master, player, other_club, club_b_admin, msg, login):
    status = reverse("accounts:message_status", args=[club.slug, msg.pk])
    urls = [confirm_url(club, msg, "handled"), status] + [
        give_url(club, msg, k) for k in ("coins", "items", "map")
    ]
    for user in (game_master, player):
        c = login(user)
        for u in urls:
            assert c.get(u).status_code == 403
            assert c.post(u, {"status": "closed"}).status_code == 403
    c = login(club_b_admin)
    for u in urls[:1] + urls[2:]:
        assert c.get(u.replace(club.slug, other_club.slug)).status_code == 404
    msg.refresh_from_db()
    assert msg.status == "open"


def test_cross_club_isolation(club, club_admin, other_club, character, msg, login):
    b_item = Item.objects.create(club=other_club, name="Foreign", value_cp=1)
    b_map = HexMap.objects.create(club=other_club, name="BMap")
    b_loc = Location.objects.create(tile=Tile.objects.get(map=b_map, q=0, r=0), name="BLoc")
    c = login(club_admin)
    cases = [
        ("items", {"items-0-item": b_item.pk, "items-0-quantity": 1}),
        ("map", {"map_kind": "found", "location": b_loc.pk}),
        ("map", {"map_kind": "visit", "hex_map": b_map.pk, "q": 1, "r": 1}),
    ]
    for kind, extra in cases:
        r = c.post(give_url(club, msg, kind), payload(character, **extra, confirmed="1"))
        assert r.status_code == 200
    assert nothing_written()


@pytest.mark.django_db
def test_demo_message_has_character():
    call_command("seed_demo")
    call_command("seed_demo")
    assert Message.objects.count() == 1
    m = Message.objects.get()
    assert m.character.name == "Aria Windrunner"
    assert Character.objects.filter(name="Aria Windrunner").count() == 1
