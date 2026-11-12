import re
from html.parser import HTMLParser

import pytest
from django.urls import reverse

from accounts import navigation

pytestmark = [pytest.mark.django_db, pytest.mark.story("U60")]

SHORTCUTS = {
    "Character": ("characters:mine", "character"),
    "Shops": ("shops:index", "town"),
    "Quests": ("quests:index", "town"),
    "Trades": ("trades:index", "trades"),
    "Map": ("map:index", "map"),
}


def home(login, user, club):
    return login(user).get(reverse("club_home", args=[club.slug])).content.decode()


def header(body):
    start = body.index('<nav class="site-header')
    return body[start : body.index("</nav>", start)]


def section(body, key):
    start = body.index(f"wm-menu-group-{key}")
    return body[start : body.index("</section>", start)]


class _Outside(HTMLParser):
    """Collect shortcut anchors and whether each sits inside .navbar-collapse."""

    def __init__(self):
        super().__init__()
        self.stack, self.found = [], []

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "input", "img", "hr", "meta", "link", "use"):
            return
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if "wm-shortcut" in classes:
            self.found.append((a, any("navbar-collapse" in c for _, c in self.stack)))
        self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break


def test_shortcuts_have_icon_label_tooltip_outside_collapse(login, club, player):
    body = header(home(login, player, club))
    tree = _Outside()
    tree.feed(body)
    by_label = {a["aria-label"]: (a, inside) for a, inside in tree.found}
    assert set(by_label) == set(SHORTCUTS)
    for label, (name, _) in SHORTCUTS.items():
        a, inside = by_label[label]
        assert inside is False
        assert "data-wm-tooltip" in a and a["title"] == label
        assert a["href"] == reverse(name, args=[club.slug])
    assert body.count("wm-shortcut-label") == 5
    assert body.index("wm-shortcuts") < body.index("navbar-collapse")
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


def test_empty_group_hidden(login, club, player, monkeypatch):
    monkeypatch.setattr(
        navigation, "_entries", [e for e in navigation._entries if e.group != "map"]
    )
    assert "wm-menu-group-map" not in header(home(login, player, club))


def test_agent_access_only_in_game_master_menu(login, club, player, game_master):
    url = reverse("agent_access:index", args=[club.slug])
    nav = header(home(login, game_master, club))
    gm = nav[nav.index("nav-gm") :]
    assert url in gm
    assert url not in nav[: nav.index("nav-gm")]
    assert url not in header(home(login, player, club))


def test_logout_last_in_account_group_by_post(login, club, player):
    body = home(login, player, club)
    account = section(body, "account")
    assert account.rstrip().endswith("</form>")
    assert 'method="post"' in account and reverse("logout") in account
    assert account.index("dropdown-divider") < account.index("<form")
    client = login(player)
    client.post(reverse("logout"))
    assert client.get(reverse("club_home", args=[club.slug])).status_code == 302


def test_club_home_follows_menu_groups(login, club, player):
    body = home(login, player, club)
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
