import datetime

import pytest
from django.core.management import call_command
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import available_coins, coin_balance, item_quantities

pytestmark = pytest.mark.django_db


def url(club, character, name):
    return reverse(f"characters:{name}", kwargs={"club_slug": club.slug, "pk": character.pk})


def payload(item=None, qty="", cp="", note="why", date="2025-01-02", **extra):
    return {
        "note": note,
        "date": date,
        "coins_cp": cp,
        "items-TOTAL_FORMS": "3",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "3",
        "items-0-item": item.pk if item else "",
        "items-0-quantity": qty,
        **extra,
    }


def entries(character):
    return LedgerEntry.objects.filter(character=character).order_by("pk")


@pytest.mark.story("U3")
@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_give_coins_and_item(request, login, club, character, item, who):
    user = request.getfixturevalue(who)
    r = login(user).post(url(club, character, "adjust"), payload(item, 2, cp=300, direction="give"))
    assert r.status_code == 302
    e = entries(character).get()
    assert e.kind == "award" and e.note == "why"
    assert e.created_by == user
    assert e.date == datetime.date(2025, 1, 2)
    assert coin_balance(character) == 300
    assert item_quantities(character)[item.pk] == 2


@pytest.mark.story("U3")
def test_get_defaults_to_today(login, game_master, club, character):
    r = login(game_master).get(url(club, character, "adjust"))
    assert r.status_code == 200
    from django.utils import timezone

    assert timezone.localdate().isoformat() in r.content.decode()


@pytest.mark.story("U14")
def test_take_defaults_to_adjustment(login, game_master, club, funded, item):
    r = login(game_master).post(
        url(club, funded, "adjust"), payload(item, 2, cp=100, direction="take")
    )
    assert r.status_code == 302
    e = entries(funded).last()
    assert e.kind == "adjustment"
    assert all(line.coins <= 0 and line.quantity <= 0 for line in e.lines.all())
    assert coin_balance(funded) == 900
    assert item_quantities(funded)[item.pk] == 3


@pytest.mark.story("U14")
def test_explicit_kind(login, game_master, club, character):
    login(game_master).post(
        url(club, character, "adjust"), payload(cp=5, direction="give", kind="adjustment")
    )
    assert entries(character).get().kind == "adjustment"


@pytest.mark.story("U3")
def test_note_required_and_empty_amounts(login, game_master, club, character, item):
    c = login(game_master)
    r = c.post(url(club, character, "adjust"), payload(item, 1, note="", direction="give"))
    assert r.status_code == 200
    r = c.post(url(club, character, "adjust"), payload(direction="give"))
    assert r.status_code == 200
    assert "at least one" in r.content.decode()
    assert not entries(character).exists()


@pytest.mark.story("U14")
def test_take_beyond_available(login, game_master, club, funded, item):
    before = entries(funded).count()
    c = login(game_master)
    r = c.post(url(club, funded, "adjust"), payload(cp=5000, direction="take"))
    assert r.status_code == 200
    r = c.post(url(club, funded, "adjust"), payload(item, 99, direction="take"))
    assert r.status_code == 200
    assert entries(funded).count() == before


@pytest.mark.story("U14")
def test_take_held_fails(login, game_master, club, funded, item, make_open_trade):
    make_open_trade(items={item: 5}, coins=1000)
    before = entries(funded).count()
    c = login(game_master)
    assert (
        c.post(url(club, funded, "adjust"), payload(item, 1, direction="take")).status_code == 200
    )
    assert c.post(url(club, funded, "adjust"), payload(cp=1, direction="take")).status_code == 200
    assert entries(funded).count() == before
    assert available_coins(funded) == 0


@pytest.mark.story("U3")
def test_retired_item_refused(login, game_master, club, character, item):
    item.retired = True
    item.save()
    c = login(game_master)
    assert item.name not in c.get(url(club, character, "adjust")).content.decode()
    r = c.post(url(club, character, "adjust"), payload(item, 1, direction="give"))
    assert r.status_code == 200
    assert not entries(character).exists()


@pytest.mark.story("U3")
@pytest.mark.story("U14")
@pytest.mark.story("U7")
@pytest.mark.parametrize("name", ["adjust", "consume"])
def test_player_forbidden(login, player, club, character, name):
    c = login(player)
    assert c.get(url(club, character, name)).status_code == 403
    assert c.post(url(club, character, name), payload(cp=1, direction="give")).status_code == 403


@pytest.mark.story("U3")
@pytest.mark.story("U7")
def test_cross_club(login, game_master, club, character, foreign_character, foreign_item):
    c = login(game_master)
    for name in ("adjust", "consume"):
        assert c.get(url(club, foreign_character, name)).status_code == 404
    r = c.post(url(club, character, "adjust"), payload(foreign_item, 1, direction="give"))
    assert r.status_code == 200
    r = c.post(url(club, character, "consume"), payload(foreign_item, 1))
    assert r.status_code == 200
    assert not entries(character).exists()


@pytest.mark.story("U7")
def test_consume(login, game_master, club, funded, item):
    r = login(game_master).post(url(club, funded, "consume"), payload(item, 2, cp=100, note=""))
    assert r.status_code == 302
    e = entries(funded).last()
    assert e.kind == "consumed" and e.note == "Consumed"
    assert all(line.coins <= 0 and line.quantity <= 0 for line in e.lines.all())
    assert coin_balance(funded) == 900
    assert item_quantities(funded)[item.pk] == 3


@pytest.mark.story("U7")
def test_consume_held_refused(login, game_master, club, funded, item, second_item, make_open_trade):
    make_open_trade(items={item: 5})
    before = entries(funded).count()
    c = login(game_master)
    assert c.post(url(club, funded, "consume"), payload(item, 1)).status_code == 200
    assert c.post(url(club, funded, "consume"), payload(second_item, 1)).status_code == 200
    assert entries(funded).count() == before


@pytest.mark.story("U7")
def test_consume_partly_held_overflow(login, game_master, club, funded, item, make_open_trade):
    make_open_trade(items={item: 3})
    before = entries(funded).count()
    r = login(game_master).post(url(club, funded, "consume"), payload(item, 4))
    assert r.status_code == 200
    assert entries(funded).count() == before


@pytest.mark.story("U3")
def test_demo_gear_idempotent(db):
    call_command("seed_demo")
    call_command("seed_demo")
    from player_characters.models import Character

    aria = Character.objects.get(name="Aria Windrunner")
    owned = {
        i.name: item_quantities(aria)[i.pk]
        for i in Item.objects.filter(club=aria.club)
        if i.pk in item_quantities(aria)
    }
    assert (owned["Rope"], owned["Healing potion"], owned["Torch"]) == (1, 2, 5)
    assert coin_balance(aria) == 5000
