"""Guards: a dead or archived character cannot file map requests."""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership, User
from map.models import MapRequest
from map.services import add_to_credit
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def _url(name, club, *args):
    return reverse(f"map:{name}", args=[club.slug, *args])


def _make_character(club, name, *, died_on=None, archived_at=None):
    user = User.objects.create_user(f"{name.lower()}@example.com", password="pw", display_name=name)
    membership = Membership.objects.create(user=user, club=club)
    character = Character.objects.create(
        club=club, owner=membership, name=name, died_on=died_on, archived_at=archived_at
    )
    return character, user


def test_visit_new_dead_refused(login, club, hex_map):
    dead, user = _make_character(club, "Dead", died_on=timezone.localdate())
    c = login(user)
    r = c.post(
        _url("request_visit", club, hex_map.pk),
        {"q": 1, "r": 0, "characters": [dead.pk], "date": "2026-01-02", "note": "n"},
    )
    assert r.status_code == 200
    assert f"{dead.name} died on {dead.died_on.isoformat()}" in r.content.decode()
    assert not MapRequest.objects.exists()


def test_visit_new_archived_refused(login, club, hex_map):
    archived, user = _make_character(club, "Archived", archived_at=timezone.now())
    c = login(user)
    r = c.post(
        _url("request_visit", club, hex_map.pk),
        {"q": 1, "r": 0, "characters": [archived.pk], "date": "2026-01-02", "note": "n"},
    )
    assert r.status_code == 200
    assert "Select a valid choice" in r.content.decode()
    assert not MapRequest.objects.exists()


def test_credit_new_dead_refused(login, club, game_master, tile_location):
    user = User.objects.create_user(
        "credit_dead@example.com", password="pw", display_name="CreditDead"
    )
    membership = Membership.objects.create(user=user, club=club, is_game_master=True)
    dead = Character.objects.create(
        club=club, owner=membership, name="CreditDead", died_on=timezone.localdate()
    )
    add_to_credit(tile_location, "discovered", [dead])
    c = login(user)
    r = c.post(
        _url("request_credit", club, "discovered", tile_location.pk),
        {"characters": [dead.pk], "date": "2026-01-02", "note": "n"},
    )
    assert r.status_code == 200
    assert f"{dead.name} died on {dead.died_on.isoformat()}" in r.content.decode()
    assert not MapRequest.objects.exists()


def test_credit_new_archived_refused(login, club, game_master, tile_location):
    user = User.objects.create_user(
        "credit_arch@example.com", password="pw", display_name="CreditArch"
    )
    membership = Membership.objects.create(user=user, club=club, is_game_master=True)
    archived = Character.objects.create(
        club=club, owner=membership, name="CreditArch", archived_at=timezone.now()
    )
    add_to_credit(tile_location, "discovered", [archived])
    c = login(user)
    r = c.post(
        _url("request_credit", club, "discovered", tile_location.pk),
        {"characters": [archived.pk], "date": "2026-01-02", "note": "n"},
    )
    assert r.status_code == 200
    assert "Select a valid choice" in r.content.decode()
    assert not MapRequest.objects.exists()


def test_mixed_pick_refused_as_a_whole(login, club, hex_map):
    dead, user = _make_character(club, "Dead", died_on=timezone.localdate())
    living = Character.objects.create(
        club=club, owner=dead.owner, name="Living", died_on=None, archived_at=None
    )
    c = login(user)
    r = c.post(
        _url("request_visit", club, hex_map.pk),
        {"q": 1, "r": 0, "characters": [living.pk, dead.pk], "date": "2026-01-02", "note": "n"},
    )
    assert r.status_code == 200
    assert f"{dead.name} died on {dead.died_on.isoformat()}" in r.content.decode()
    assert not MapRequest.objects.exists()


def test_living_character_still_files_visit(login, club, hex_map, player, character):
    c = login(player)
    r = c.post(
        _url("request_visit", club, hex_map.pk),
        {"q": 1, "r": 0, "characters": [character.pk], "date": "2026-01-02", "note": "n"},
    )
    assert r.status_code == 302
    assert MapRequest.objects.count() == 1
    req = MapRequest.objects.get()
    assert req.kind == "visit"
