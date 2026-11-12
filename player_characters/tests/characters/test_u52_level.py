import pytest
from django.core.management import call_command
from django.urls import reverse

from player_characters.models import Character

pytestmark = pytest.mark.story("U52")


def u(name, club, pk=None):
    kw = {"club_slug": club.slug}
    if pk is not None:
        kw["pk"] = pk
    return reverse(name, kwargs=kw)


def edit(login, user, club, character, **data):
    return login(user).post(u("characters:edit", club, character.pk), {"name": "Aria", **data})


@pytest.mark.parametrize("who", ["player", "game_master", "club_admin"])
def test_can_set_level(club, login, request, character, who):
    r = edit(login, request.getfixturevalue(who), club, character, level="5")
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.level == 5


def test_other_player_refused(club, login, other_player, character):
    assert login(other_player).get(u("characters:edit", club, character.pk)).status_code == 403
    assert edit(login, other_player, club, character, level="5").status_code == 403
    character.refresh_from_db()
    assert character.level is None


@pytest.mark.parametrize("bad", ["0", "-3"])
def test_non_positive_refused(club, login, player, character, bad):
    Character.objects.filter(pk=character.pk).update(level=2)
    r = edit(login, player, club, character, level=bad)
    assert r.status_code == 200
    character.refresh_from_db()
    assert character.level == 2


def test_blank_saves_none(club, login, player, character):
    Character.objects.filter(pk=character.pk).update(level=2)
    edit(login, player, club, character, level="")
    character.refresh_from_db()
    assert character.level is None


def test_create_with_level(club, login, game_master, player):
    from accounts.models import Membership

    owner = Membership.objects.get(club=club, user=player).pk
    r = login(game_master).post(
        u("characters:create", club), {"name": "New", "owner": owner, "level": "3"}
    )
    assert r.status_code == 302
    assert Character.objects.get(name="New").level == 3


def test_sheet_header(club, login, player, character):
    url = u("characters:detail", club, character.pk)
    body = login(player).get(url).content.decode()
    assert "Level &mdash;" in body or "Level —" in body and "Level None" not in body
    Character.objects.filter(pk=character.pk).update(level=5)
    assert "Level 5" in login(player).get(url).content.decode()


@pytest.mark.parametrize("page", ["characters:directory", "characters:index"])
def test_lists(club, login, game_master, character, page):
    url = u(page, club)
    assert "Level 5" not in login(game_master).get(url).content.decode()
    Character.objects.filter(pk=character.pk).update(level=5)
    assert "Level 5" in login(game_master).get(url).content.decode()


@pytest.mark.parametrize("page", ["characters:directory", "characters:index"])
def test_lists_hide_other_club(club, login, game_master, foreign_character, page):
    Character.objects.filter(pk=foreign_character.pk).update(level=9)
    body = login(game_master).get(u(page, club)).content.decode()
    assert "Level 9" not in body and "Fenn" not in body


def test_demo_levels_idempotent(club):

    call_command("seed_demo")
    call_command("seed_demo")
    levels = dict(Character.objects.values_list("name", "level"))
    assert levels.get("Aria Windrunner") == 5
