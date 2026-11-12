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
    for url in (reverse("home"), reverse("club_home", args=[club.slug])):
        html = client.get(url).content.decode()
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
    # "account" is filled by the Menu template (Log out); "primary" by icon shortcuts (U60).
    assert {e.group for e in navigation._entries} == set(navigation.GROUPS) - {"account", "primary"}


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
