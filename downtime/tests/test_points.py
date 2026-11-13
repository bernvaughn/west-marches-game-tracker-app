from datetime import date
from unittest import mock

import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Club, Membership, User
from downtime import services
from downtime.models import DowntimePointEntry
from player_characters.models import Character

pytestmark = [pytest.mark.story("D1"), pytest.mark.django_db]


@pytest.fixture
def second(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")


def url(club):
    return reverse("downtime:points_award", args=[club.slug])


def post(client, club, chars, **extra):
    data = {
        "characters": [c.pk for c in chars],
        "direction": "give",
        "points": 2,
        "note": "Well played",
        "date": "2026-11-01",
    }
    data.update(extra)
    return client.post(url(club), data)


@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_award_two_characters(who, request, club, login, character, second):
    user = request.getfixturevalue(who)
    resp = post(login(user), club, [character, second])
    assert resp.status_code == 302
    entries = DowntimePointEntry.objects.all()
    assert entries.count() == 2
    e = entries[0]
    assert (e.kind, e.delta, e.note, e.date, e.created_by) == (
        "award",
        2,
        "Well played",
        date(2026, 11, 1),
        user,
    )
    assert services.balance(character) == 2 == services.balance(second)


def test_remove_and_refuse_below_zero(club, login, game_master, character):
    c = login(game_master)
    post(c, club, [character], points=3)
    post(c, club, [character], direction="take", points=1)
    assert DowntimePointEntry.objects.filter(kind="remove", delta=-1).count() == 1
    resp = post(c, club, [character], direction="take", points=5)
    assert resp.status_code == 200
    assert "enough downtime points" in resp.content.decode()
    assert services.balance(character) == 2


def test_players_and_anonymous_refused(club, login, player, client):
    c = login(player)
    assert c.get(url(club)).status_code == 403
    assert c.post(url(club), {}).status_code == 403
    assert client.get(url(club)).status_code == 302


def test_cross_club_refused(club, other_club, login, game_master, other_club_character):
    resp = post(login(game_master), club, [other_club_character])
    assert resp.status_code == 200
    assert not DowntimePointEntry.objects.exists()
    gm2 = User.objects.create_user("gm2@example.com", password="pw", display_name="G2")
    Membership.objects.create(user=gm2, club=other_club, is_game_master=True)
    assert login(gm2).get(url(club)).status_code == 404


def test_prefill_and_redirect_to_sheet(club, login, game_master, character):
    c = login(game_master)
    assert (
        f'value="{character.pk}"' in c.get(url(club), {"character": character.pk}).content.decode()
    )
    resp = c.post(
        url(club) + f"?character={character.pk}",
        {
            "characters": [character.pk],
            "direction": "give",
            "points": 1,
            "note": "x",
            "date": "2026-11-01",
        },
    )
    assert resp.url == reverse("characters:detail", args=[club.slug, character.pk])


def test_sheet_shows_balance(club, login, game_master, character):
    services.award(character, 4, "x", by=game_master, club=club)
    sheet = reverse("characters:detail", args=[club.slug, character.pk])
    html = login(game_master).get(sheet).content.decode()
    assert "Downtime points" in html and "Award points" in html
    assert "Spend" not in html.split("Downtime points")[1].split("</dl>")[0]
    with mock.patch("downtime.templatetags.downtime_points.reverse", return_value="/play/"):
        html = login(game_master).get(sheet).content.decode()
    assert 'href="/play/"' in html


def history_url(club, character):
    return reverse("ledger:character_history", args=[club.slug, character.pk])


def test_history_and_kind_filter(club, login, game_master, character):
    services.award(character, 3, "big win", by=game_master, club=club)
    services.award(character, -1, "oops", by=game_master, club=club, kind="remove")
    c = login(game_master)
    html = c.get(history_url(club, character)).content.decode()
    assert "big win" in html and "oops" in html
    html = c.get(history_url(club, character), {"points_kind": "remove"}).content.decode()
    assert "oops" in html and "big win" not in html


def test_club_ledger_and_isolation(
    club, other_club, login, game_master, character, other_club_character
):
    services.award(character, 3, "zq-mine", by=game_master, club=club)
    services.award(other_club_character, 7, "zq-theirs", by=None, club=other_club)
    c = login(game_master)
    ledger = reverse("ledger:index", args=[club.slug])
    html = c.get(ledger).content.decode()
    assert "zq-mine" in html and "zq-theirs" not in html
    assert "zq-mine" not in c.get(ledger, {"points_kind": "remove"}).content.decode()
    # history of another club's character is not reachable
    other = reverse("ledger:character_history", args=[club.slug, other_club_character.pk])
    assert c.get(other).status_code == 404


def test_seed_demo_idempotent(db):
    call_command("seed_demo")
    call_command("seed_demo")
    aria = Character.objects.get(name="Aria Windrunner")
    assert services.balance(aria) == 2
    assert Club.objects.count() >= 1
