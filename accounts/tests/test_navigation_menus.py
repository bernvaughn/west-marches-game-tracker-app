import pathlib
import re
from html.parser import HTMLParser

import pytest
from django.urls import reverse

from accounts import navigation

pytestmark = pytest.mark.django_db

ROOT = pathlib.Path(__file__).resolve().parents[2]


def page(login, user, club):
    return login(user).get(reverse("club_home", args=[club.slug])).content.decode()


def q(url):
    return f'href="{url}"'


def hrefs(body):
    return set(re.findall(r'href="([^"]+)"', body))


def nav_html(body):
    start = body.index('id="site-header-menu"')
    return body[start : body.index("</nav>", start)]


GM_ONLY = ("agent_access:batches", "agent_access:connections")


@pytest.mark.story("U29")
def test_player_sees_primary_and_more_only(login, club, player):
    nav = nav_html(page(login, player, club))
    for label in ("Character", "Shops", "Quests", "More"):
        assert f">{label}</a>" in nav
    assert "Game master" not in nav and "Club admin" not in nav
    for name in (
        "accounts:whitelist",
        "accounts:message_inbox",
        "shops:manage_list",
        "map:map_create",
        *GM_ONLY,
    ):
        assert q(reverse(name, args=[club.slug])) not in nav
    assert q(reverse("map:requests", args=[club.slug])) in nav


@pytest.mark.story("U29")
def test_game_master_menu(login, club, game_master):
    nav = nav_html(page(login, game_master, club))
    assert "Game master" in nav and "Club admin" not in nav
    for name in (
        "map:requests",
        "map:map_create",
        "agent_access:batches",
        "agent_access:proposed_items",
    ):
        assert q(reverse(name, args=[club.slug])) in nav


@pytest.mark.story("U29")
def test_club_admin_menus(login, club, club_admin):
    nav = nav_html(page(login, club_admin, club))
    assert "Club admin" in nav and "Game master" in nav
    assert q(reverse("accounts:whitelist", args=[club.slug])) in nav
    assert q(reverse("agent_access:proposed_items", args=[club.slug])) in nav
    for name in GM_ONLY:
        assert q(reverse(name, args=[club.slug])) not in nav
    assert q(reverse("site_clubs")) not in nav


@pytest.mark.story("U29")
def test_site_admin_sees_everything(login, club, site_admin):
    from accounts.models import Membership

    Membership.objects.create(user=site_admin, club=club)
    nav = nav_html(page(login, site_admin, club))
    assert q(reverse("site_clubs")) in nav and reverse("site_settings") in nav
    for name in GM_ONLY:
        assert q(reverse(name, args=[club.slug])) in nav


@pytest.mark.story("U29")
def test_empty_group_hidden(login, club, game_master, monkeypatch):
    monkeypatch.setattr(navigation, "_entries", [e for e in navigation._entries if e.group != "gm"])
    assert "Game master" not in nav_html(page(login, game_master, club))


@pytest.mark.story("U29")
def test_old_nav_links_still_reachable(login, club, player, club_admin, game_master):
    expected = {
        "player": [
            "accounts:index",
            "accounts:message_new",
            "characters:index",
            "characters:create",
            "characters:transfer_start",
            "trades:index",
            "trades:propose",
            "items:index",
            "shops:index",
            "ledger:index",
            "map:index",
            "map:requests",
            "quests:index",
            "agent_access:index",
        ],
        "admin": [
            "accounts:whitelist",
            "accounts:message_inbox",
            "shops:manage_list",
            "shops:rotation_list",
            "quests:manage",
            "agent_access:proposed_items",
            "items:index",
            "accounts:index",
        ],
        "gm": ["agent_access:connections", "agent_access:batches", "agent_access:proposed_items"],
    }
    users = {"player": player, "admin": club_admin, "gm": game_master}
    for who, names in expected.items():
        links = hrefs(nav_html(page(login, users[who], club)))
        for name in names:
            assert reverse(name, args=[club.slug]) in links, (who, name)
        assert reverse("password_change") in links


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.inside = [], {}

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "input", "img", "hr", "meta", "link"):
            return
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        in_collapse = any(c for _, c in self.stack if "navbar-collapse" in c)
        for key in (
            "user-name",
            "club-name",
            "character-selector",
            "character-name",
            "approvals-menu",
            "logout",
            "nav-more",
            "nav-gm",
        ):
            if key in classes:
                self.inside[key] = in_collapse
        self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break


@pytest.mark.story("U34")
def test_always_visible_items_outside_collapse(login, club, game_master, character):

    body = page(login, game_master, club)
    header = body[
        body.index('<nav class="site-header') : body.index(
            "</nav>", body.index('<nav class="site-header')
        )
    ]
    tree = _Tree()
    tree.feed(header)
    for key in ("user-name", "club-name", "character-name", "logout"):
        assert tree.inside.get(key) is False, key
    assert tree.inside["nav-more"] is True and tree.inside["nav-gm"] is True


@pytest.mark.story("U34")
def test_approvals_menu_outside_collapse(login, club, game_master, player):

    body = page(login, game_master, club)
    if "approvals-menu" in body:
        tree = _Tree()
        tree.feed(body)
        assert tree.inside["approvals-menu"] is False


@pytest.mark.story("U29")
def test_cross_club_nav_has_no_other_club(login, club, other_club, player):
    assert other_club.slug not in nav_html(page(login, player, club))


@pytest.mark.story("U29")
def test_no_nav_partials_remain():
    skip = {".venv", "node_modules", ".git"}
    found = [p for p in ROOT.rglob("_nav.html") if not skip & set(p.parts)]
    assert found == []
