import pytest
from django.urls import reverse

from accounts.models import Membership
from player_characters.models import Character


def u(name, club, pk=None):
    kw = {"club_slug": club.slug}
    if pk is not None:
        kw["pk"] = pk
    return reverse(name, kwargs=kw)


def mid(club, user):
    return Membership.objects.get(club=club, user=user).pk


@pytest.mark.story("U2")
def test_player_owner_fixed(club, login, player, other_player):
    r = login(player).post(
        u("characters:create", club), {"name": "New", "owner": mid(club, other_player)}
    )
    c = Character.objects.get(name="New")
    assert r.status_code == 302
    assert c.owner.user == player and c.club == club


@pytest.mark.story("U2")
@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_privileged_create_for_member(club, login, request, other_player, who):
    r = login(request.getfixturevalue(who)).post(
        u("characters:create", club), {"name": "New", "owner": mid(club, other_player)}
    )
    assert r.status_code == 302
    assert Character.objects.get(name="New").owner.user == other_player


@pytest.mark.story("U2")
def test_site_admin_must_pick_owner(club, login, site_admin):
    r = login(site_admin).post(u("characters:create", club), {"name": "New"})
    assert r.status_code == 200
    assert not Character.objects.filter(name="New").exists()


@pytest.mark.story("U2")
def test_owner_choices_exclude_other_club(club, login, club_admin, foreign_member, other_club):
    foreign = Membership.objects.get(club=other_club, user=foreign_member).pk
    r = login(club_admin).post(u("characters:create", club), {"name": "New", "owner": foreign})
    assert r.status_code == 200
    assert not Character.objects.filter(name="New").exists()


@pytest.mark.story("U2")
@pytest.mark.parametrize("who", ["player", "game_master", "club_admin", "site_admin"])
def test_edit_allowed(club, login, request, character, who):
    owner = character.owner
    r = login(request.getfixturevalue(who)).post(
        u("characters:edit", club, character.pk),
        {"name": "Renamed", "description": "n"},
    )
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.name == "Renamed" and character.description == "n"
    assert character.owner == owner


@pytest.mark.story("U2")
def test_edit_forbidden_for_other_player(club, login, other_player, character):
    c = login(other_player)
    assert c.get(u("characters:edit", club, character.pk)).status_code == 403
    assert c.post(u("characters:edit", club, character.pk), {"name": "X"}).status_code == 403


@pytest.mark.story("U2")
def test_foreign_member_404(club, login, foreign_member, character):
    c = login(foreign_member)
    assert c.get(u("characters:edit", club, character.pk)).status_code == 404
