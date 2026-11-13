import pytest
from django.urls import reverse

from accounts import navigation

pytestmark = [pytest.mark.django_db, pytest.mark.story("U61")]


def home(login, user, club):
    return login(user).get(reverse("club_home", args=[club.slug])).content.decode()


def bar(body):
    start = body.index('<nav class="site-header')
    return body[start : body.index("</nav>", start)]


def panel(body):
    return body[body.index('id="site-menu"') :]


def test_hamburger_first_club_name_second_no_brand(login, club, player):
    body = home(login, player, club)
    b = bar(body)
    assert b.index("wm-hamburger") < b.index("club-switcher") < b.index("wm-shortcuts")
    assert "West Marches" not in b
    assert "<title>" in body and "West Marches" in body[: body.index("</title>")]
    assert 'id="site-menu-title">West Marches<' in body


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
    pos = [b.index(f"wm-shortcut-rank-{i}") for i in range(1, 6)]
    assert pos == sorted(pos)
    assert b.count("data-wm-tooltip") == 5 and b.count("wm-shortcut-label") == 5


def test_groups_per_role(login, club, player, game_master, club_admin):
    p = panel(home(login, player, club))
    assert "wm-menu-group-gm" not in p and "wm-menu-group-admin" not in p
    assert "Game master" in panel(home(login, game_master, club))
    assert "Club admin" in panel(home(login, club_admin, club))


def test_empty_group_hidden(login, club, player, monkeypatch):
    monkeypatch.setattr(
        navigation, "_entries", [e for e in navigation._entries if e.group != "trades"]
    )
    assert "wm-menu-group-trades" not in home(login, player, club)


def test_logout_is_last_post_form(login, club, club_admin):
    p = panel(home(login, club_admin, club))
    p = p[: p.index("</form>")]
    assert p.rindex("Club admin") < p.index('action="{}"'.format(reverse("logout")))
    assert p.count("<form") == 1 and 'method="post"' in p


def test_no_club_user_gets_panel_and_logout(login, player):
    body = login(player).get(reverse("home")).content.decode()
    assert 'aria-label="Open menu"' in bar(body)
    assert "Log out" not in bar(body)
    assert reverse("logout") in panel(body) and "wm-menu-group-account" in panel(body)


def test_site_admin_without_club_sees_site_links(login, site_admin):
    p = panel(login(site_admin).get(reverse("home")).content.decode())
    assert reverse("site_clubs") in p and reverse("site_settings") in p
