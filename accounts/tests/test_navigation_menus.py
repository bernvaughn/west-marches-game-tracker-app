import pathlib
import re
from html.parser import HTMLParser

import pytest
from django.test import RequestFactory
from django.urls import reverse

from accounts import navigation
from accounts.apps import is_admin, is_gm, is_gm_or_admin, is_member

pytestmark = pytest.mark.django_db

ROOT = pathlib.Path(__file__).resolve().parents[2]


def page(login, user, club):
    return login(user).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()


def q(url):
    return f'href="{url}"'


def hrefs(body):
    return set(re.findall(r'href="([^"]+)"', body))


def nav_html(body):
    start = body.index('id="site-menu"')
    return body[start : body.index("wm-menu-logout", start)]


GM_ONLY = ("agent_access:batches", "agent_access:connections")


@pytest.mark.story("U29")
def test_player_sees_menu_only(login, club, player):
    nav = nav_html(page(login, player, club))
    assert "wm-menu-group-character" in nav
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
            "characters:mine",
            "characters:directory",
            "characters:create",
            "items:index",
            "shops:index",
            "ledger:index",
            "map:index",
            "map:requests",
            "quests:index",
        ],
        "admin": [
            "accounts:whitelist",
            "accounts:message_inbox",
            "shops:manage_list",
            "shops:rotation_list",
            "quests:manage",
            "agent_access:proposed_items",
            "agent_access:index",
            "items:index",
            "accounts:index",
            "characters:index",
        ],
        "gm": [
            "agent_access:index",
            "agent_access:connections",
            "agent_access:batches",
            "agent_access:proposed_items",
            "characters:index",
        ],
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
        in_collapse = any(c for _, c in self.stack if "offcanvas" in c)
        for key in (
            "user-name",
            "club-name",
            "character-selector",
            "character-name",
            "approvals-menu",
            "logout",
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
    for key in ("user-name", "club-name", "character-name"):
        assert tree.inside.get(key) is False, key
    assert "logout" not in tree.inside  # U61: Log out lives in the side panel
    for dead in ("nav-menu", "nav-gm", "nav-admin", "navbar-collapse"):
        assert dead not in header


@pytest.mark.story("U34")
def test_busy_header_keeps_everything_outside_collapse(login, club, club_admin, player):
    """A GM/admin with approvals and several characters still gets every top-bar item."""
    from accounts.models import Membership, Message
    from player_characters.models import Character

    admin_m = Membership.objects.get(user=club_admin, club=club)
    admin_m.is_game_master = True
    admin_m.save()
    for name in ("Thaddeus Longername the Third", "Second"):
        Character.objects.create(club=club, owner=admin_m, name=name)
    sender = Membership.objects.get(user=player, club=club)
    Message.objects.create(club=club, sender=sender, body="hi")
    body = page(login, club_admin, club)
    header = body[: body.index("</nav>", body.index('<nav class="site-header'))]
    tree = _Tree()
    tree.feed(header)
    for key in ("user-name", "club-name", "character-selector", "approvals-menu"):
        assert tree.inside.get(key) is False, key
    assert "Log out" not in header  # U61: in the side panel


@pytest.mark.story("U29")
def test_cross_club_nav_has_no_other_club(login, club, other_club, player):
    assert other_club.slug not in nav_html(page(login, player, club))


@pytest.mark.story("U29")
def test_no_nav_partials_remain():
    skip = {".venv", "node_modules", ".git"}
    found = [p for p in ROOT.rglob("_nav.html") if not skip & set(p.parts)]
    assert found == []


@pytest.mark.story("U168")
def test_nav_entry_and_link_audience_default_to_player():
    assert navigation.NavEntry("club", "People", "accounts:index", None, 100).audience == "player"
    assert navigation.NavLink("People", "/club/", "accounts:index", False).audience == "player"


@pytest.mark.story("U168")
@pytest.mark.parametrize(
    "group,check,expected",
    [
        ("admin", is_admin, "admin"),
        ("gm", is_gm_or_admin, "gm"),  # owner's rule: open to both -> gm
        ("gm", is_gm, "gm"),
        ("club", is_member, "player"),
        ("account", lambda r: True, "player"),
        ("gm", lambda r: True, "gm"),  # group fallback
        ("admin", lambda r: True, "admin"),
    ],
)
def test_derive_audience(group, check, expected):
    assert navigation._derive_audience(group, check) == expected


@pytest.mark.story("U168")
def test_registered_entries_keep_their_audience(club, game_master, club_admin):
    from accounts.models import Membership

    factory = RequestFactory()
    for user in (game_master, club_admin):
        request = factory.get(reverse("club_home", args=[club.slug]))
        request.user = user
        request.club = club
        request.membership = Membership.objects.get(user=user, club=club)
        nav = navigation.entries_for(request)
        for group, links in nav.items():
            expected = "gm" if group == "gm" else ("admin" if group == "admin" else "player")
            assert all(link.audience == expected for link in links)


@pytest.mark.story("U168")
def test_gm_links_carry_gm_colour_and_mark(login, club, game_master):
    nav = nav_html(
        login(game_master).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    )
    assert "wm-nav-link-gm" in nav and "wm-nav-mark-gm" in nav
    assert '<span class="wm-nav-mark wm-nav-mark-gm">GM</span>' in nav
    assert "wm-nav-link-admin" not in nav


@pytest.mark.story("U168")
def test_admin_links_carry_admin_colour_and_mark(login, club, club_admin):
    nav = nav_html(
        login(club_admin).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    )
    assert "wm-nav-link-admin" in nav and "wm-nav-mark-admin" in nav
    assert '<span class="wm-nav-mark wm-nav-mark-admin">Admin</span>' in nav


@pytest.mark.story("U168")
def test_player_sees_no_colour_mark_or_key(login, club, player):
    nav = nav_html(
        login(player).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    )
    assert "wm-nav-link-gm" not in nav and "wm-nav-link-admin" not in nav
    assert "wm-nav-mark" not in nav
    assert "wm-menu-group-key" not in nav


@pytest.mark.story("U168")
def test_key_shows_only_roles_the_person_has(
    login, club, player, game_master, club_admin, site_admin
):
    gm_nav = nav_html(
        login(game_master).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    )
    assert "wm-menu-group-key" in gm_nav
    assert "wm-nav-key-swatch-gm" in gm_nav
    assert "wm-nav-key-swatch-admin" not in gm_nav

    admin_nav = nav_html(
        login(club_admin).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    )
    assert "wm-nav-key-swatch-admin" in admin_nav

    player_nav = nav_html(
        login(player).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    )
    assert "wm-menu-group-key" not in player_nav

    super_nav = nav_html(
        login(site_admin).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    )
    assert "wm-nav-key-swatch-gm" in super_nav and "wm-nav-key-swatch-admin" in super_nav


@pytest.mark.story("U168")
def test_gm_or_admin_links_show_as_gm_for_club_admin_too(login, club, club_admin):
    # Owner's rule: a link open to both GMs and club admins shows as GM use.
    nav = nav_html(
        login(club_admin).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    )
    assert "wm-nav-link-gm" in nav and "wm-nav-mark-gm" in nav


def h2_texts(body):
    """Extract h2 heading texts from the page body, excluding the site menu title."""
    texts = []
    for match in re.finditer(r"<h2[^>]*>(.*?)</h2>", body, re.DOTALL):
        if 'id="site-menu-title"' in match.group(0):
            continue
        inner = match.group(1)
        text = re.sub(r"<[^>]+>", "", inner)
        text = " ".join(text.split())
        if text:
            texts.append(text)
    return texts


@pytest.mark.story("U60")
def test_club_home_headings_appear_once(login, club, player, game_master, club_admin, site_admin):
    """Each club home section heading appears exactly once (C2 / U60)."""
    for user in (player, game_master, club_admin, site_admin):
        body = page(login, user, club)
        headings = h2_texts(body)
        for heading in headings:
            assert headings.count(heading) == 1, f"Duplicate heading: {heading!r}"
        assert "Game master" not in headings, headings
        assert "Club admin" not in headings, headings


@pytest.mark.story("U60")
def test_club_home_gm_admin_links_appear_once(login, club, game_master, club_admin):
    """GM and Admin section links still appear on the club home (C2 / U60)."""
    gm_urls = [
        reverse("agent_access:index", args=[club.slug]),
        reverse("map:requests", args=[club.slug]),
        reverse("characters:index", args=[club.slug]),
    ]
    admin_urls = [
        reverse("accounts:whitelist", args=[club.slug]),
        reverse("shops:manage_list", args=[club.slug]),
        reverse("quests:manage", args=[club.slug]),
        reverse("items:index", args=[club.slug]),
    ]

    body = page(login, game_master, club)
    for url in gm_urls:
        assert url in body, f"GM link missing: {url}"

    body = page(login, club_admin, club)
    for url in admin_urls:
        assert url in body, f"Admin link missing: {url}"
