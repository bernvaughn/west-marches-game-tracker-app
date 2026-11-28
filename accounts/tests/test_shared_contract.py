from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.template import engines
from django.test import override_settings
from django.urls import reverse

from accounts import navigation
from accounts.htmx import render_modal_or_page
from accounts.permissions import is_game_master

pytestmark = pytest.mark.django_db

LOCMEM = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {"frag.html": "FRAGMENT", "page.html": "FULLPAGE"},
                )
            ]
        },
    }
]


@pytest.mark.story("U33")
def test_render_modal_or_page(rf):
    with override_settings(TEMPLATES=LOCMEM):
        engines._engines = {}
        htmx = render_modal_or_page(rf.get("/", HTTP_HX_REQUEST="true"), "frag.html", "page.html")
        plain = render_modal_or_page(rf.get("/"), "frag.html", "page.html")
    engines._engines = {}
    assert htmx.content == b"FRAGMENT"
    assert plain.content == b"FULLPAGE"
    assert "HX-Request" in htmx["Vary"] and "HX-Request" in plain["Vary"]


@pytest.mark.story("U33")
def test_base_has_modal_and_assets(login, player, club):
    client = login(player)
    # Home page (no club)
    html = client.get(reverse("home")).content.decode()
    assert 'id="app-modal"' in html and "modal-content" in html
    assert "css/coins.css" in html and "js/modal.js" in html
    # Club home - players are redirected to dashboard, follow redirect
    html = client.get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    assert 'id="app-modal"' in html and "modal-content" in html
    assert "css/coins.css" in html and "js/modal.js" in html
    assert finders.find("js/modal.js") and finders.find("css/coins.css")
    js = open(finders.find("js/modal.js")).read()
    for text in ("appModalClose", "htmx:afterSwap", "app-modal"):
        assert text in js


@pytest.fixture
def registry(monkeypatch):
    entries = []
    monkeypatch.setattr(navigation, "_entries", entries)
    return entries


def _req(rf, user, club):
    request = rf.get("/")
    request.user = user
    request.club = club
    return request


@pytest.mark.story("U29")
def test_real_registry_has_all_groups():
    # Every registered group is a known group; "primary" holds no entry (it is
    # filled by icon shortcuts at render time); every MENU_GROUPS key exists.
    registered = {e.group for e in navigation._entries}
    assert "primary" not in registered
    assert registered <= set(navigation.GROUPS)
    assert {k for k, _h, _i in navigation.MENU_GROUPS} <= set(navigation.GROUPS)


@pytest.mark.story("U29")
def test_menu_groups_icons_in_sprite():
    sprite = finders.find("vendor/bootstrap-icons-1.11.3/bootstrap-icons.svg")
    assert sprite is not None, "bootstrap-icons sprite not found"
    svg = Path(sprite).read_text()
    for key, _heading, icon in navigation.MENU_GROUPS:
        assert f'id="{icon}"' in svg, f"group {key!r} icon {icon!r} missing from sprite"


@pytest.mark.story("U29")
def test_checks_order_and_groups(registry, rf, club, other_club, player, game_master):
    navigation.register("gm", "Zeta", "club_home", lambda r: is_game_master(r.user, r.club), 2)
    navigation.register("primary", "B", "club_home", None, 5)
    navigation.register("town", "Late", "club_home", None, 9)
    navigation.register("town", "Early", "club_home", None, 1)  # duplicate ignored
    gm = navigation.entries_for(_req(rf, game_master, club))
    assert list(gm) == list(navigation.GROUPS)
    assert [link.label for link in gm["gm"]] == ["Zeta"]
    assert gm["gm"][0].url == reverse("club_home", args=[club.slug])
    assert [link.label for link in gm["town"]] == ["Late"]
    assert navigation.entries_for(_req(rf, player, club))["gm"] == []
    assert navigation.entries_for(_req(rf, game_master, other_club))["gm"] == []


@pytest.mark.story("U29")
def test_sorted_by_order_then_label(registry, rf, club, player):
    navigation.register("primary", "B", "club_home", None, 1)
    navigation._entries.append(navigation.NavEntry("primary", "A", "club_home", None, 1))
    navigation._entries.append(navigation.NavEntry("primary", "C", "club_home", None, 0))
    labels = [link.label for link in navigation.entries_for(_req(rf, player, club))["primary"]]
    assert labels == ["C", "A", "B"]


@pytest.mark.story("U29")
def test_unknown_group_and_no_club(registry, rf, player):
    with pytest.raises(ValueError):
        navigation.register("nope", "X", "club_home")
    navigation.register("primary", "X", "club_home")
    assert all(v == [] for v in navigation.entries_for(_req(rf, player, None)).values())


def _match(view_name):
    return type("Match", (), {"view_name": view_name})()


@pytest.mark.story("U121")
def test_also_current_marks_dashboard_on_club_home(rf, club, player):
    # apps.py registers Dashboard with also_current=("club_home",).
    from accounts.models import Membership

    req = _req(rf, player, club)
    req.membership = Membership.objects.get(user=player, club=club)

    def dash(view_name):
        req.resolver_match = _match(view_name)
        links = navigation.entries_for(req)["primary"]
        return next(link for link in links if link.url_name == "accounts:player_dashboard")

    assert dash("accounts:player_dashboard").active is True
    assert dash("club_home").active is True
    assert dash("characters:mine").active is False
    # The match uses the full name, so a club_home in another namespace does not count.
    assert dash("shops:club_home").active is False


@pytest.mark.story("U121")
def test_namespaced_entry_is_current(registry, rf, club, player):
    navigation.register("primary", "Shops", "shops:index")
    req = _req(rf, player, club)
    req.resolver_match = _match("shops:index")
    assert [link.active for link in navigation.entries_for(req)["primary"]] == [True]
    req.resolver_match = None
    assert [link.active for link in navigation.entries_for(req)["primary"]] == [False]
