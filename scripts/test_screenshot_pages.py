"""Smoke test: every page in the screenshot page list returns 200. No browser."""

import pytest
from django.core.management import call_command

from accounts.models import User
from scripts.screenshot_pages import PAGES, ROLES, demo_objects, extra_fixtures


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
    assert {"shops-buy-modal", "map-tile-modal", "inbox-grant-modal", "topbar-menu-open"} <= names


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_page_returns_200(client, demo, page):
    email = ROLES[page.role]
    if email:
        client.force_login(User.objects.get(email=email))
    assert client.get(page.url(demo)).status_code == 200
    if page.modal_url:
        resp = client.get(page.modal_url(demo), HTTP_HX_REQUEST="true")
        assert resp.status_code == 200
