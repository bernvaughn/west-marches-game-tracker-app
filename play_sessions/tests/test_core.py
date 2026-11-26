from datetime import datetime

import pytest
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import core
from play_sessions.models import PlaySession
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("P1")]


def test_from_club_local_to_club_local_round_trip():
    club = Club.objects.create(
        name="Round Trip Club", slug="round-trip", timezone="America/Chicago"
    )
    naive = datetime(2024, 6, 15, 14, 30)  # 2:30 PM CDT
    utc = core.from_club_local(club, naive)
    assert utc.tzinfo is not None
    back = core.to_club_local(club, utc)
    assert back.replace(tzinfo=None) == naive


def test_from_club_local_rejects_aware_input():
    club = Club.objects.create(name="Aware Club", slug="aware", timezone="UTC")
    aware = timezone.now()
    with pytest.raises(ValueError, match="requires a naive datetime"):
        core.from_club_local(club, aware)


def test_to_club_local_rejects_naive_input():
    club = Club.objects.create(name="Naive Club", slug="naive", timezone="UTC")
    naive = datetime(2024, 6, 15, 14, 30)
    with pytest.raises(ValueError, match="requires an aware datetime"):
        core.to_club_local(club, naive)


def test_can_manage_sessions():
    club = Club.objects.create(name="Manage Club", slug="manage")
    other_club = Club.objects.create(name="Other Club", slug="other")

    admin_user = User.objects.create_user(email="admin@test.com", password="pass12345678")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    other_gm_user = User.objects.create_user(email="othergm@test.com", password="pass12345678")
    superuser = User.objects.create_superuser(email="super@test.com", password="pass12345678")

    Membership.objects.create(user=admin_user, club=club, is_club_admin=True)
    Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    Membership.objects.create(user=player_user, club=club)
    Membership.objects.create(user=other_gm_user, club=other_club, is_game_master=True)

    assert core.can_manage_sessions(admin_user, club) is True
    assert core.can_manage_sessions(gm_user, club) is True
    assert core.can_manage_sessions(player_user, club) is False
    assert core.can_manage_sessions(other_gm_user, club) is False
    assert core.can_manage_sessions(superuser, club) is True


def test_character_is_active_returns_true():
    club = Club.objects.create(name="Active Club", slug="active")
    membership = Membership.objects.create(
        user=User.objects.create_user(email="u@test.com", password="pass12345678"),
        club=club,
    )
    character = Character.objects.create(name="Char", club=club, owner=membership)
    assert core.character_is_active(character) is True


def test_attendance_saved_signal_delivers_kwargs():
    received = {}

    def handler(sender, **kwargs):
        received.update(kwargs)

    core.attendance_saved.connect(handler)
    try:
        club = Club.objects.create(name="Signal Club", slug="signal")
        membership = Membership.objects.create(
            user=User.objects.create_user(email="gm@test.com", password="pass12345678"),
            club=club,
            is_game_master=True,
        )
        character = Character.objects.create(name="Hero", club=club, owner=membership)
        session = PlaySession.objects.create(
            club=club, title="Session", starts_at=timezone.now(), game_master=membership
        )

        core.attendance_saved.send(
            sender=None, session=session, characters=[character], by=membership.user
        )

        assert received["session"] == session
        assert received["characters"] == [character]
        assert received["by"] == membership.user
    finally:
        core.attendance_saved.disconnect(handler)


def test_discovery_loads_module_and_skips_missing(tmp_path, monkeypatch):
    # Create a temporary package structure
    pkg_dir = tmp_path / "test_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")

    # Feature 'a' has both modules
    (pkg_dir / "urls_a.py").write_text("urlpatterns = ['a_url']\n")
    (pkg_dir / "hooks_a.py").write_text("def register(): pass\n")

    # Feature 'b' has neither
    monkeypatch.syspath_prepend(str(tmp_path))

    # Should load 'a'
    urls_a = core.discover_module("a", "urls", package="test_pkg")
    assert urls_a is not None
    assert urls_a.urlpatterns == ["a_url"]

    hooks_a = core.discover_module("a", "hooks", package="test_pkg")
    assert hooks_a is not None

    # Should skip missing 'b'
    urls_b = core.discover_module("b", "urls", package="test_pkg")
    assert urls_b is None

    hooks_b = core.discover_module("b", "hooks", package="test_pkg")
    assert hooks_b is None


def test_discovery_module_is_in_sys_modules_and_runs_once(tmp_path, monkeypatch):
    import sys

    pkg_dir = tmp_path / "once_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    counter = tmp_path / "counter.txt"
    (pkg_dir / "urls_a.py").write_text(
        f"open({str(counter)!r}, 'a').write('x')\nurlpatterns = ['u']\npublic_urlpatterns = ['p']\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in ("once_pkg", "once_pkg.urls_a"):
        monkeypatch.delitem(sys.modules, name, raising=False)

    first = core.discover_module("a", "urls", package="once_pkg")
    second = core.discover_module("a", "urls", package="once_pkg")

    assert first is second
    assert sys.modules["once_pkg.urls_a"] is first
    assert counter.read_text() == "x"


def test_discovery_broken_module_raises(tmp_path, monkeypatch):
    pkg_dir = tmp_path / "bad_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "urls_bad.py").write_text("raise ImportError('broken')\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ImportError, match="broken"):
        core.discover_module("bad", "urls", package="bad_pkg")


def test_collect_urlpatterns_concatenates():
    # Uses the real FEATURES and discovers nothing (no urls_<feature> modules exist)
    patterns = core.collect_urlpatterns("urlpatterns")
    assert isinstance(patterns, list)


def test_load_hooks_calls_register(monkeypatch):
    # Create a fake hooks module for one feature
    import play_sessions.core as core_module

    called = {}

    class FakeModule:
        def register(self):
            called["yes"] = True

    monkeypatch.setattr(
        core_module,
        "discover_module",
        lambda f, p, pkg=None: FakeModule() if f == "schedule" else None,
    )
    core_module.load_hooks()
    assert called.get("yes") is True


def test_features_content():
    assert core.FEATURES == (
        "schedule",
        "calendar",
        "rsvp",
        "attendance",
        "report",
        "recap",
        "settings",
    )
