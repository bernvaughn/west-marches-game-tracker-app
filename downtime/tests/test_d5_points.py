import re

import pytest
from django.urls import reverse

from accounts.models import Membership, User
from downtime.models import DowntimePointEntry
from player_characters.models import Character

pytestmark = [pytest.mark.story("D5"), pytest.mark.django_db]

SENTENCE = "Earned downtime during a session? Ask your game master for the points."


@pytest.fixture
def second(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.fixture
def foreign(other_club):
    user = User.objects.create_user("f@example.com", password="pw", display_name="F")
    m = Membership.objects.create(user=user, club=other_club)
    return Character.objects.create(club=other_club, owner=m, name="Zed")


def sheet(client, club, char):
    return client.get(reverse("characters:detail", args=[club.slug, char.pk])).content.decode()


def award_url(club):
    return reverse("downtime:points_award", args=[club.slug])


def request_url(club):
    return reverse("downtime:request_new", args=[club.slug])


def test_owner_sees_request_link(club, login, player, character):
    html = sheet(login(player), club, character)
    assert "Request points" in html
    assert SENTENCE in html
    assert f"{request_url(club)}?character={character.pk}" in html


@pytest.mark.parametrize("who", ["game_master", "club_admin", "other_player"])
def test_others_do_not_see_link(who, request, club, login, character):
    html = sheet(login(request.getfixturevalue(who)), club, character)
    assert "Request points" not in html
    assert SENTENCE not in html


def _checked(html):
    return set(re.findall(r'name="characters"[^>]*value="(\d+)"[^>]*checked', html))


def test_request_preselect(club, login, player, character):
    html = login(player).get(f"{request_url(club)}?character={character.pk}").content.decode()
    assert _checked(html) == {str(character.pk)} or f'value="{character.pk}" checked' in html


def test_request_preselect_ignores_others(club, login, player, character, second, foreign):
    c = login(player)
    for pk in (second.pk, foreign.pk, "abc"):
        resp = c.get(f"{request_url(club)}?character={pk}")
        assert resp.status_code == 200
        assert f'value="{pk}" checked' not in resp.content.decode()


def test_award_page_lists_club_characters(club, login, game_master, character, second, foreign):
    html = login(game_master).get(award_url(club)).content.decode()
    assert "Aria" in html and "Borin" in html and "Zed" not in html
    for text in ("Select all", "Clear", 'name="points"', 'name="note"', 'name="date"'):
        assert text in html


def test_bulk_award_once_each(club, login, club_admin, character, second):
    other = Character.objects.create(club=club, owner=character.owner, name="Cy")
    resp = login(club_admin).post(
        award_url(club),
        {
            "characters": [character.pk, second.pk, other.pk, character.pk],
            "direction": "give",
            "points": 2,
            "note": "Session",
            "date": "2026-11-01",
        },
    )
    assert resp.status_code == 302
    assert DowntimePointEntry.objects.count() == 3
    assert DowntimePointEntry.objects.filter(character=character).count() == 1


def test_permissions(club, login, player, client, character):
    assert login(player).get(award_url(club)).status_code == 403
    assert login(player).post(award_url(club), {}).status_code == 403
    assert client.get(award_url(club)).status_code in (302, 403)


def test_cross_club_award_refused(club, login, game_master, foreign):
    resp = login(game_master).post(
        award_url(club),
        {
            "characters": [foreign.pk],
            "direction": "give",
            "points": 1,
            "note": "x",
            "date": "2026-11-01",
        },
    )
    assert resp.status_code == 200
    assert DowntimePointEntry.objects.count() == 0
