import pytest
from django.test import Client

from accounts.models import Club, Membership, User
from character_options.models import Background, CharacterClass, Species
from character_options.services import seed_default_options
from items.models import Item
from player_characters.models import Character


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings):
    """Hash passwords with MD5 in tests.

    Django's default PBKDF2 hasher is deliberately slow, and every user-creating
    fixture pays that cost. Tests only need passwords to round-trip, not to be secure.
    """
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def club(db):
    club = Club.objects.create(name="Club A", slug="club-a")
    seed_default_options(club)
    return club


@pytest.fixture
def unseeded_club(db):
    return Club.objects.create(name="Club A", slug="club-a")


@pytest.fixture
def other_club(db):
    club = Club.objects.create(name="Club B", slug="club-b")
    seed_default_options(club)
    return club


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


@pytest.fixture
def species(club):
    # Get the seeded Elf species
    return Species.objects.for_club(club).get(name__iexact="Elf")


@pytest.fixture
def char_class(club):
    # Get the seeded Fighter class
    return CharacterClass.objects.for_club(club).get(name__iexact="Fighter")


@pytest.fixture
def background(club):
    # Get the seeded Soldier background
    return Background.objects.for_club(club).get(name__iexact="Soldier")