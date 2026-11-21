"""Browser regression test: an expanded "Preview contents" stays open.

The shop page used to poll #stock every 5 s and replace it with htmx, which
removed the `open` attribute from any expanded `<details class="wm-loot-stock-preview">`.
The poll is gone, so the stock fragment is only re-fetched after the player's
own buy/sell (via `shopStockChanged from:body`). An expanded preview must stay
open while the player reads it.

The login view rate-limits after two logins, so the player is signed in with a
session cookie made via `force_login`. Browser tests need Chromium and are run
with `-m browser`; they are excluded from the default test run.
"""

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import Club, Membership, User
from items.models import Item
from items.tests.factories import add_slot, make_container
from player_characters.models import Character
from shops.models import Rotation, Shop, ShopStock

CLUB_SLUG = "demo"


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _make_shop_with_container():
    """Create a club, a player with one character, and an open shop stocking a container."""
    club = Club.objects.create(name="Demo", slug=CLUB_SLUG)
    user = User.objects.create_user("alice@example.com", password="demo-password")
    Membership.objects.create(user=user, club=club)
    # Exactly one owned character -> auto-selected for this club.
    Character.objects.create(
        club=club, owner=Membership.objects.get(user=user, club=club), name="Aria"
    )
    container = make_container(club, name="Burglar's Pack", is_container=True)
    crowbar = Item.objects.create(club=club, name="Crowbar", value_cp=100)
    add_slot(container, [(crowbar, 1, 1, 1)], chance_pct=100)
    rotation = Rotation.objects.create(club=club, name="Always", open_date=timezone.localdate())
    shop = Shop.objects.create(club=club, name="General Store")
    rotation.shops.add(shop)
    ShopStock.objects.create(shop=shop, item=container, quantity=2)
    return club, user, shop


class _ShopPage:
    """A Playwright page on a shop."""

    def __init__(self, pw, live_server, session_id):
        self.browser = pw.chromium.launch()
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 800})
        self.context.add_cookies(
            [{"name": "sessionid", "value": session_id, "url": live_server.url}]
        )
        self.page = self.context.new_page()
        self.console = []
        self.page.on("console", lambda msg: self.console.append(msg.text))

    def wait(self, seconds):
        # page.wait_for_timeout pumps the Playwright event loop.
        self.page.wait_for_timeout(int(seconds * 1000))

    def close(self):
        self.context.close()
        self.browser.close()


@pytest.mark.browser
@pytest.mark.django_db
def test_expanded_preview_stays_open(live_server):
    """An expanded "Preview contents" <details> stays open past 6 s (no poll)."""
    club, user, shop = _make_shop_with_container()
    session_id = _session_id(user)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        sp = _ShopPage(pw, live_server, session_id)
        try:
            sp.page.goto(f"{live_server.url}/c/{club.slug}/shops/{shop.id}/")
            sp.page.wait_for_load_state("networkidle")
            # Expand the preview on the container row.
            sp.page.locator("details.wm-loot-stock-preview summary").first.click()
            details = sp.page.locator("details.wm-loot-stock-preview").first
            assert details.get_attribute("open") is not None, "Preview did not expand"
            sp.wait(6.5)
            assert details.get_attribute("open") is not None, "Preview collapsed on its own"
            assert not any("CSP" in m or "unsafe-eval" in m for m in sp.console), (
                f"Console CSP/eval errors: {sp.console}"
            )
        finally:
            sp.close()
