import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from accounts import navigation

pytestmark = [pytest.mark.django_db, pytest.mark.story("U61")]

SHORTCUTS = {
    "Dashboard": ("accounts:player_dashboard", "character"),
    "Character": ("characters:mine", "character"),
    "Map": ("map:index", "map"),
    "Quests": ("quests:index", "town"),
    "Sessions": ("play_sessions:calendar", "club"),
    "Shops": ("shops:index", "town"),
    "Downtime": ("downtime:play", "town"),
}


def home(login, user, club):
    # Follow redirect for players (dashboard)
    return login(user).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()


def site_home(login, user):
    return login(user).get(reverse("home")).content.decode()


def bar(body):
    start = body.index('<nav class="site-header')
    return body[start : body.index("</nav>", start)]


def panel(body):
    return body[body.index('id="site-menu"') :]


def section(body, key):
    start = body.index(f"wm-menu-group-{key}")
    return body[start : body.index("</section>", start)]


class _Outside(HTMLParser):
    """Collect shortcut anchors and whether each sits inside the offcanvas."""

    def __init__(self):
        super().__init__()
        self.stack, self.found = [], []

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "input", "img", "hr", "meta", "link", "use"):
            return
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if "wm-shortcut" in classes:
            self.found.append((a, any("offcanvas" in c for _, c in self.stack)))
        self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break


def test_shortcuts_have_icon_label_tooltip_outside_collapse(login, club, player):
    body = bar(home(login, player, club))
    tree = _Outside()
    tree.feed(body)
    by_label = {a["aria-label"]: (a, inside) for a, inside in tree.found}
    assert set(by_label) == set(SHORTCUTS)
    for label, (name, _) in SHORTCUTS.items():
        a, inside = by_label[label]
        assert inside is False
        assert "data-wm-tooltip" in a and a["title"] == label
        assert a["href"] == reverse(name, args=[club.slug])
    assert "<svg" in body[body.index("nav-link wm-shortcut") : body.index("wm-shortcut-label")]


def test_each_shortcut_also_in_its_menu_group(login, club, player):
    body = home(login, player, club)
    for name, key in SHORTCUTS.values():
        assert f'href="{reverse(name, args=[club.slug])}"' in section(body, key)


def test_player_menu_groups(login, club, player):
    body = home(login, player, club)
    assert 'href="{}"'.format(reverse("ledger:index", args=[club.slug])) in section(
        body, "character"
    )
    assert 'href="{}"'.format(reverse("map:requests", args=[club.slug])) in section(body, "map")
    club_group = section(body, "club")
    for name in ("accounts:index", "items:index", "accounts:message_new"):
        assert reverse(name, args=[club.slug]) in club_group
    assert ">Message the admins<" in club_group


def test_admin_does_not_get_people_or_items_in_club_group(login, club, club_admin):
    body = home(login, club_admin, club)
    group = section(body, "club") if "wm-menu-group-club" in body else ""
    for name in ("accounts:index", "items:index"):
        assert f'href="{reverse(name, args=[club.slug])}"' not in group


def test_agent_access_only_in_game_master_menu(login, club, player, game_master):
    url = reverse("agent_access:index", args=[club.slug])
    body = home(login, game_master, club)
    assert url in section(body, "gm")
    assert url not in bar(body)
    assert url not in home(login, player, club)


def test_logout_last_in_panel_by_post(login, club, club_admin):
    body = home(login, club_admin, club)
    account = section(body, "account")
    panel_body = panel(body)
    head = panel_body[: panel_body.index("</form>")]
    form = head[head.index('<form method="post"') :]
    assert reverse("logout") in form
    assert head.count("<form") == 1 and "wm-menu-logout" in form
    assert 'method="post"' in head
    assert "Log out" not in account
    assert head.rindex("Club admin") < head.index('action="{}"'.format(reverse("logout")))
    client = login(club_admin)
    client.post(reverse("logout"))
    assert client.get(reverse("club_home", args=[club.slug])).status_code == 302


def test_club_home_follows_menu_groups(login, club, game_master):
    # Only GMs/admins see the menu groups on club_home
    body = home(login, game_master, club)
    main = body[body.index("<main") :]
    for _, heading in navigation.MENU_GROUPS:
        if heading != "Account":
            assert re.search(rf">\s*{heading}\s*<", main), heading
    assert "Account" not in re.sub(r"<[^>]+>", " ", main)


def test_registry_icon_adds_shortcut(registry_empty, rf, club, player):
    navigation.register("town", "B", "club_home", None, 5, icon="shop", shortcut_order=2)
    navigation.register("map", "A", "club_home", None, 1, icon="map", shortcut_order=1)
    navigation.register("map", "Plain", "quests:index", None, 3)
    request = rf.get("/")
    request.user, request.club = player, club
    result = navigation.entries_for(request)
    assert [link.label for link in result["primary"]] == ["A", "B"]
    assert [link.label for link in result["town"]] == ["B"]
    assert result["primary"][0].icon == "map"


@pytest.fixture
def registry_empty(monkeypatch):
    monkeypatch.setattr(navigation, "_entries", [])


def test_hamburger_first_club_name_second_no_brand(login, club, player):
    body = home(login, player, club)
    b = bar(body)
    assert b.index("wm-hamburger") < b.index("club-switcher") < b.index("wm-shortcuts")
    assert "Downtime Market" not in b and "West Marches" not in b
    assert "<title>" in body and "Downtime Market" in body[: body.index("</title>")]
    assert 'id="site-menu-title">Downtime Market<' in body


def test_hamburger_accessibility_and_panel(login, club, player):
    body = home(login, player, club)
    assert 'aria-label="Open menu"' in bar(body)
    assert 'aria-controls="site-menu"' in bar(body)
    assert 'class="offcanvas offcanvas-start' in body and 'id="site-menu"' in body


def test_no_dropdown_menus_in_bar(login, club, club_admin):
    b = bar(home(login, club_admin, club))
    for dead in ("nav-menu", "nav-gm", "nav-admin", ">Menu<", "navbar-collapse", "Club admin"):
        assert dead not in b


def test_shortcut_ranks_in_order(login, club, player):
    b = bar(home(login, player, club))
    pos = [b.index(f"wm-shortcut-rank-{i}") for i in range(1, 7)]
    assert pos == sorted(pos)
    assert b.count("data-wm-tooltip") >= 7


@pytest.mark.story("U121")
def test_dashboard_is_first_shortcut(login, club, player):
    b = bar(home(login, player, club))
    # Dashboard is rank 1, should appear first
    assert b.index("wm-shortcut-rank-1") < b.index("wm-shortcut-rank-2")
    # Verify it has the right href and attributes
    assert 'aria-label="Dashboard"' in b
    assert f'href="/c/{club.slug}/accounts/dashboard/"' in b
    assert 'title="Dashboard"' in b
    assert "data-wm-tooltip" in b


@pytest.mark.story("U121")
def test_dashboard_current_on_dashboard_page(login, club, player, character):
    body = (
        login(player)
        .get(reverse("accounts:player_dashboard", args=[club.slug]), follow=True)
        .content.decode()
    )
    b = bar(body)
    dash_rank1 = b[b.index("wm-shortcut-rank-1") : b.index("wm-shortcut-rank-2")]
    assert 'aria-current="page"' in dash_rank1


@pytest.mark.story("U121")
def test_dashboard_current_on_club_home_for_gm_admin(login, club, game_master, club_admin):
    # GMs and admins with no selected character see club_home instead of dashboard
    for user in (game_master, club_admin):
        body = (
            login(user).get(reverse("club_home", args=[club.slug]), follow=False).content.decode()
        )
        b = bar(body)
        dash_rank1 = b[b.index("wm-shortcut-rank-1") : b.index("wm-shortcut-rank-2")]
        assert 'aria-current="page"' in dash_rank1, f"Dashboard not current for {user}"


@pytest.mark.story("U121")
def test_dashboard_shows_for_gm_and_admin(login, club, game_master, club_admin):
    for user in (game_master, club_admin):
        body = home(login, user, club)
        b = bar(body)
        assert 'aria-label="Dashboard"' in b
        assert f'href="/c/{club.slug}/accounts/dashboard/"' in b


def test_groups_per_role(login, club, player, game_master, club_admin):
    p = panel(home(login, player, club))
    assert "wm-menu-group-gm" not in p and "wm-menu-group-admin" not in p
    assert "Game master" in panel(home(login, game_master, club))
    assert "Club admin" in panel(home(login, club_admin, club))


def test_empty_group_hidden(login, club, player, monkeypatch):
    monkeypatch.setattr(
        navigation, "_entries", [e for e in navigation._entries if e.group != "map"]
    )
    assert "wm-menu-group-map" not in home(login, player, club)


def test_no_club_user_gets_panel_and_logout(login, player):
    body = login(player).get(reverse("home")).content.decode()
    assert 'aria-label="Open menu"' in bar(body)
    assert "Log out" not in bar(body)
    assert reverse("logout") in panel(body) and "wm-menu-group-account" in panel(body)


def test_site_admin_without_club_sees_site_links(login, site_admin):
    p = panel(login(site_admin).get(reverse("home")).content.decode())
    assert reverse("site_clubs") in p and reverse("site_settings") in p


def test_nowrap_beats_bootstrap_flex_wrap_inherit(login, club, player):
    """Bootstrap sets flex-wrap: inherit at (0,2,0); our nowrap rule must match it."""
    b = bar(home(login, player, club))
    assert re.match(r'<nav class="site-header[^>]*>\s*<div class="container-fluid wm-topbar"', b)
    css = (Path(settings.BASE_DIR) / "static/css/components.css").read_text()
    rule = re.search(r"\.site-header > \.wm-topbar \{([^}]*)\}", css)
    assert rule and "flex-wrap: nowrap" in rule.group(1)


def test_skip_link_and_main_id(login, player):
    html = site_home(login, player)
    assert 'href="#main"' in html
    assert html.index('href="#main"') < html.index('<nav class="site-header')
    assert '<main id="main"' in html


def test_icon_only_buttons_have_tooltips(login, player):
    html = site_home(login, player)
    assert 'title="Open menu" data-wm-tooltip' in html
    assert 'title="Close menu" data-wm-tooltip' in html


@pytest.mark.story("U121")
def test_character_picker_and_club_name_truncate_on_phone():
    css = Path("static/css/components.css").read_text()
    picker = css[css.index(".site-header .character-selector .character-name-text {") :]
    picker = picker[: picker.index("}")]
    for rule in ("overflow: hidden", "text-overflow: ellipsis", "white-space: nowrap"):
        assert rule in picker
    assert ".site-header .character-selector .dropdown-toggle { display: inline-flex" in css
    phone = css[css.index("@media (max-width: 575.98px) {\n  .site-header") :]
    phone = phone[: phone.index("\n}")]
    # The club name stays on a phone (U32); it is cut short, not hidden.
    assert ".club-switcher { display: none" not in phone
    assert ".club-name { max-width:" in phone
    assert ".character-selector .dropdown-toggle { max-width:" in phone
