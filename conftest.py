import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.test import Client

from accounts.models import Club, Membership, User
from agent_access.tokens import create_token
from character_options.models import Background, CharacterClass, Species
from items.models import Item
from items.tests.factories import make_container as _make_container
from items.tests.factories import make_diplomats_pack
from player_characters.models import Character

# Configure shared browser environment for all browser tests
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from browser_env import use_shared_browser  # noqa: E402

use_shared_browser()


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings):
    """Hash passwords with MD5 in tests.

    Django's default PBKDF2 hasher is deliberately slow, and every user-creating
    fixture pays that cost. Tests only need passwords to round-trip, not to be secure.
    """
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


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


@pytest.fixture
def make_container(db):
    """Create a container item in a club; delegates to the shared factory."""

    def _make(club, name="Mystery Box", **kw):
        return _make_container(club, name=name, **kw)

    return _make


@pytest.fixture
def diplomats_pack(db, club):
    """Diplomat's Pack fixture: fixed, ranged, 50%, weighted and unknown slots."""

    return make_diplomats_pack(club)


@pytest.fixture
def species(club):
    return Species.objects.create(club=club, name="Elf")


@pytest.fixture
def char_class(club):
    return CharacterClass.objects.create(club=club, name="Fighter")


@pytest.fixture
def background(club):
    return Background.objects.create(club=club, name="Soldier")


@pytest.fixture
def make_pure_item():
    """Factory for pure ``SimpleNamespace`` items used by property tests."""

    def _make(value_cp, value_units, name="Thing", unit_name="unit", stacked=True):
        return SimpleNamespace(
            name=name,
            unit_name=unit_name,
            value_cp=value_cp,
            value_units=value_units,
            is_stacked=stacked,
        )

    return _make


@pytest.fixture
def make_db_item(club):
    """Factory for DB-backed stacked items used by property tests."""

    def _make(value_cp, value_units, name="Thing", unit_name="unit"):
        return Item.objects.create(
            club=club,
            name=name,
            is_stacked=True,
            unit_name=unit_name,
            value_cp=value_cp,
            value_units=value_units,
        )

    return _make


MCP_HEADERS = {
    "HTTP_ACCEPT": "application/json, text/event-stream",
    "HTTP_MCP_PROTOCOL_VERSION": "2025-11-25",
}


@pytest.fixture
def gm_connection(game_master, club):
    return create_token(game_master, club, "Test agent")


@pytest.fixture
def mcp_raw():
    def call(secret, body, headers=None):
        extra = dict(MCP_HEADERS)
        if secret is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {secret}"
        extra.update(headers or {})
        return Client().post(
            "/mcp", data=json.dumps(body), content_type="application/json", **extra
        )

    return call


@pytest.fixture
def mcp(mcp_raw):
    def call(secret, tool, **arguments):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        response = mcp_raw(secret, body)
        data = response.json()
        return response.status_code, data.get("result", data)

    return call
