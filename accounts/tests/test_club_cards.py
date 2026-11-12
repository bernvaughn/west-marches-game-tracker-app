import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import Club, Membership, User
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("U28")]


def body(login, user):
    return login(user).get(reverse("home")).content.decode()


def test_player_card(login, club, player, game_master, other_player, club_admin, character):
    b = body(login, player)
    assert "Club A" in b and "Player" in b and "GM" in b
    assert "Aria" in b
    assert "1 player</p>" not in b  # player + other_player
    assert "2 players" in b


def test_roles_labels(login, club, game_master, club_admin):
    assert "Game master" in body(login, game_master)
    b = body(login, club_admin)
    assert "Club admin" in b
    assert "0 players" in b


def test_no_emails_or_inventory(login, club, player, game_master, other_player, character):
    b = body(login, player)
    for e in ("gm@example.com", "player@example.com", "other@example.com"):
        assert e not in b
    assert "Rope" not in b


def test_blank_gm_name_never_shows_email(login, club, player):
    u = User.objects.create_user("blank@example.com", password="pw", display_name="")
    Membership.objects.create(user=u, club=club, is_game_master=True)
    b = body(login, player)
    assert "blank@example.com" not in b
    assert "Unnamed game master" in b


def test_cross_club_isolation(
    login, club, other_club, player, character, club_b_member, club_b_admin
):
    gm = User.objects.create_user("bgm@example.com", password="pw", display_name="BGM")
    bm = Membership.objects.create(user=gm, club=other_club, is_game_master=True)
    Character.objects.create(club=other_club, owner=bm, name="Zed")
    mate = Membership.objects.create(
        user=User.objects.create_user("m@example.com", password="pw", display_name="Mate"),
        club=club,
    )
    Character.objects.create(club=club, owner=mate, name="Mates Hero")
    b = body(login, player)
    assert "Club B" not in b and "BGM" not in b and "Zed" not in b
    assert "Mates Hero" not in b


def _make_clubs(n, user):
    for i in range(n):
        c = Club.objects.create(name=f"C{i}", slug=f"c{i}")
        m = Membership.objects.create(user=user, club=c)
        g = User.objects.create_user(f"g{i}@x.com", password="pw", display_name=f"G{i}")
        Membership.objects.create(user=g, club=c, is_game_master=True)
        Character.objects.create(club=c, owner=m, name=f"Char{i}")


def _count(client):
    with CaptureQueriesContext(connection) as ctx:
        client.get(reverse("home"))
    return len(ctx)


def test_query_count_flat(login, db):
    u1 = User.objects.create_user("u1@x.com", password="pw", display_name="U1")
    u2 = User.objects.create_user("u2@x.com", password="pw", display_name="U2")
    _make_clubs(1, u1)
    for i in range(4):
        c = Club.objects.create(name=f"D{i}", slug=f"d{i}")
        m = Membership.objects.create(user=u2, club=c)
        Character.objects.create(club=c, owner=m, name=f"X{i}")
    _count(login(u1))  # warm up lazy SiteSettings row
    one = _count(login(u1))
    four = _count(login(u2))
    assert one == four


def test_layout(login, club, player):
    b = body(login, player)
    assert "row-cols-1" in b and "stretched-link" in b
    assert reverse("club_home", args=[club.slug]) in b


def test_site_admin_sees_all(login, site_admin, club, other_club):
    b = body(login, site_admin)
    assert "Club A" in b and "Club B" in b


def test_empty(login, db):
    u = User.objects.create_user("e@x.com", password="pw", display_name="E")
    assert "You are not in any club yet." in body(login, u)
