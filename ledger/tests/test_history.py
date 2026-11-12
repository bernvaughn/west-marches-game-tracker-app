import datetime
import re

import pytest
from django.urls import reverse

from accounts.models import Membership, User
from ledger.services import Line, record
from player_characters.models import Character

pytestmark = [pytest.mark.story("C5"), pytest.mark.django_db]


def hist(club, character):
    return reverse("ledger:character_history", args=[club.slug, character.pk])


def d(day):
    return datetime.date(2025, 1, day)


def test_newest_first(login, player, club, character):
    record(character, "award", [Line(coins=1)], note="older", date=d(1))
    record(character, "award", [Line(coins=1)], note="same-a", date=d(5))
    record(character, "award", [Line(coins=1)], note="same-b", date=d(5))
    record(character, "award", [Line(coins=1)], note="newest", date=d(9))
    html = login(player).get(hist(club, character)).content.decode()
    pos = [html.index(n) for n in ("newest", "same-b", "same-a", "older")]
    assert pos == sorted(pos)


def test_row_content_and_gm_name(login, player, game_master, club, character, item):
    record(
        character,
        "award",
        [Line(item=item, quantity=3), Line(coins=1250)],
        note="Dragon hoard",
        date=d(2),
        actor=game_master,
    )
    html = login(player).get(hist(club, character)).content.decode()
    html = re.sub(r"<[^>]+>", "", html)
    for s in ("2025-01-02", "Award", "Dragon hoard", "+3 Rope", "+12 gp 5 sp", "GM"):
        assert s in html


def test_negative_coins_show_sign_once(login, player, club, character):
    record(character, "award", [Line(coins=500)])
    record(character, "adjustment", [Line(coins=-200)], note="fee")
    html = login(player).get(hist(club, character)).content.decode()
    assert "-2 gp" in re.sub(r"<[^>]+>", "", html) and "--" not in html


def test_system_agent_and_reverses(login, player, club, character, item):
    entry = record(character, "award", [Line(item=item, quantity=1)], via_agent=True)
    rev = record(character, "reversal", [Line(item=item, quantity=-1)], reverses=entry)
    html = login(player).get(hist(club, character)).content.decode()
    assert "System" in html
    assert "agent" in html
    assert f"reverses #{entry.pk}" in html
    assert f"#{rev.pk}" in html


def test_access_matrix(
    login, club, character, player, game_master, club_admin, site_admin, other_player
):
    url = hist(club, character)
    for u in (player, game_master, club_admin, site_admin):
        assert login(u).get(url).status_code == 200
    assert login(other_player).get(url).status_code == 403


def test_cross_club(login, club, other_club, character):
    outsider = User.objects.create_user("x@example.com", password="pw")
    Membership.objects.create(user=outsider, club=other_club)
    assert login(outsider).get(hist(club, character)).status_code == 404


def test_other_club_character_under_club_url_404(login, club, other_club, club_admin):
    owner = Membership.objects.create(
        user=User.objects.create_user("y@example.com", password="pw"), club=other_club
    )
    foreign = Character.objects.create(club=other_club, owner=owner, name="Zed")
    url = reverse("ledger:character_history", args=[club.slug, foreign.pk])
    assert login(club_admin).get(url).status_code == 404


def test_other_characters_not_shown(login, player, club, character, other_character):
    record(other_character, "award", [Line(coins=1)], note="secret-note")
    record(character, "award", [Line(coins=1)], note="mine")
    html = login(player).get(hist(club, character)).content.decode()
    assert "mine" in html and "secret-note" not in html


def test_pagination(login, player, club, character):
    for i in range(51):
        record(character, "award", [Line(coins=1)], note=f"n{i}", date=d(1) + datetime.timedelta(i))
    c = login(player)
    r1 = c.get(hist(club, character))
    assert len(r1.context["entries"]) == 50
    r2 = c.get(hist(club, character) + "?page=2")
    assert len(r2.context["entries"]) == 1


def test_no_n_plus_one(login, player, club, character, item, second_item):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def count(n):
        for _ in range(n):
            record(
                character,
                "award",
                [Line(item=item, quantity=1), Line(item=second_item, quantity=1)],
            )
        c = login(player)
        with CaptureQueriesContext(connection) as ctx:
            assert c.get(hist(club, character)).status_code == 200
        return len(ctx)

    few = count(3)
    many = count(7)
    assert many <= few


def test_index_scoping(
    login,
    club,
    other_club,
    player,
    other_player,
    game_master,
    club_admin,
    character,
    other_character,
):
    owner = Membership.objects.create(
        user=User.objects.create_user("z@example.com", password="pw"), club=other_club
    )
    Character.objects.create(club=other_club, owner=owner, name="Foreign")
    url = reverse("ledger:index", args=[club.slug])
    html = login(player).get(url).content.decode()
    assert "Aria" in html and "Borin" not in html
    assert hist(club, character) in html
    for u in (game_master, club_admin):
        html = login(u).get(url).content.decode()
        assert "Aria" in html and "Borin" in html and "Foreign" not in html
