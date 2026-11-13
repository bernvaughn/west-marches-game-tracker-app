"""Smoke test: every page in the screenshot page list returns 200. No browser."""

from urllib.parse import urlsplit

import pytest
from django.core.management import call_command
from django.urls import get_resolver, resolve

from accounts.models import Membership, User
from scripts.screenshot_pages import (
    EXCLUDED,
    MODAL_ACTIONS,
    MODAL_SELECTORS,
    PAGES,
    ROLES,
    demo_objects,
    extra_fixtures,
)


@pytest.fixture
def demo(db):
    call_command("seed_demo", verbosity=0)
    extra_fixtures()
    return demo_objects()


def test_names_are_unique():
    names = [p.name for p in PAGES]
    assert len(names) == len(set(names))


def test_has_required_pages():
    names = {p.name for p in PAGES}
    assert {
        "shops-buy-modal",
        "map-tile-modal",
        "inbox-grant-modal",
        "topbar-menu-open",
        "shops-sell-junk-modal",
        "shops-sell-modal",
        "characters-junk-modal",
        "inbox-give-items-modal",
    } <= names


def _url_names(resolver=None, ns=""):
    """Every named non-admin URL pattern, as `namespace:name`."""
    resolver = resolver or get_resolver()
    out = set()
    for p in resolver.url_patterns:
        if hasattr(p, "url_patterns"):
            if p.namespace == "admin":
                continue
            out |= _url_names(p, f"{ns}{p.namespace}:" if p.namespace else ns)
        elif p.name:
            out.add(f"{ns}{p.name}")
    return out


def _covered(demo):
    names = set()
    for p in PAGES:
        for url in (p.url, p.modal_url):
            if url:
                names.add(resolve(urlsplit(url(demo)).path).view_name)
    return names


def test_every_get_url_is_covered_or_excluded(demo):
    missing = _url_names() - _covered(demo) - EXCLUDED.keys()
    assert not missing, f"Add to PAGES, or to EXCLUDED with a reason: {sorted(missing)}"


def test_excluded_is_clean(demo):
    names = _url_names()
    for name, reason in EXCLUDED.items():
        assert reason.strip() and "\n" not in reason, name
        assert name in names, f"stale EXCLUDED entry {name}"
    assert not EXCLUDED.keys() & _covered(demo)


def test_modal_actions_have_selectors():
    actions = {p.action for p in PAGES} - {None, "menu_open"}
    assert actions <= MODAL_ACTIONS
    assert set(MODAL_SELECTORS) <= actions


def test_extra_fixtures_idempotent(db):
    from downtime.models import DowntimePointRequest, DowntimeResult
    from player_characters.models import JunkMark, Trade

    call_command("seed_demo", verbosity=0)
    assert not User.objects.filter(email__in=["gm-only@example.com", "clubadmin@example.com"])
    extra_fixtures()
    counts = lambda: (  # noqa: E731
        User.objects.count(),
        Membership.objects.count(),
        JunkMark.objects.count(),
        DowntimePointRequest.objects.count(),
        DowntimeResult.objects.count(),
        Trade.objects.count(),
    )
    first = counts()
    extra_fixtures()
    assert counts() == first
    gm_only = Membership.objects.get(user__email="gm-only@example.com")
    assert gm_only.is_game_master and not gm_only.is_club_admin
    admin = Membership.objects.get(user__email="clubadmin@example.com")
    assert admin.is_club_admin and not admin.is_game_master


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_page_returns_200(client, demo, page):
    email = ROLES[page.role]
    if email:
        client.force_login(User.objects.get(email=email))
    assert client.get(page.url(demo)).status_code == 200
    if page.modal_url:
        resp = client.get(page.modal_url(demo), HTTP_HX_REQUEST="true")
        assert resp.status_code == 200
