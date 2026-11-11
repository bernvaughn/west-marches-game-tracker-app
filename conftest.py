import pytest
from django.test import Client

from accounts.models import Club, Membership, User
from items.models import Item
from player_characters.models import Character


@pytest.fixture
def club(db):
    return Club.objects.create(name="Club A", slug="club-a")


@pytest.fixture
def other_club(db):
    return Club.objects.create(name="Club B", slug="club-b")


def _user(email, name, **extra):
    return User.objects.create_user(email, password="pw", display_name=name, **extra)


@pytest.fixture
def site_admin(db):
    return User.objects.create_superuser("site@example.com", password="pw", display_name="Site")


def _member(club, email, name, **flags):
    user = _user(email, name)
    Membership.objects.create(user=user, club=club, **flags)
    return user


@pytest.fixture
def club_admin(club):
    return _member(club, "admin@example.com", "Admin", is_club_admin=True)


@pytest.fixture
def game_master(club):
    return _member(club, "gm@example.com", "GM", is_game_master=True)


@pytest.fixture
def player(club):
    return _member(club, "player@example.com", "Player")


@pytest.fixture
def other_player(club):
    return _member(club, "other@example.com", "Other")


@pytest.fixture
def character(club, player):
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Aria")


@pytest.fixture
def item(club):
    return Item.objects.create(club=club, name="Rope", value_cp=100)


@pytest.fixture
def login():
    def _login(user):
        client = Client()
        client.force_login(user)
        return client

    return _login
