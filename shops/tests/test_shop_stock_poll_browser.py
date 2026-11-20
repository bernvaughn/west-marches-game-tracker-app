"""Browser regression test: shop stock live refresh polls while the tab is visible.

Covers the fix for the CSP-blocked htmx trigger filters (the [..] filters in
`hx-trigger` need `unsafe-eval`, which the app CSP does not allow). The poll is
now driven by static JS: a setInterval and a visibilitychange listener dispatch a
`shopStockPoll` event on `#stock`, whose `hx-trigger` listens for it. The CSP is
unchanged and no `Function()` / eval is used.

The app CSP has no `unsafe-eval`, so Playwright's `wait_for_function` cannot run;
this test polls with `page.evaluate`-style waiting instead. The login view
rate-limits after two logins, so the player is signed in with a session cookie
made via `force_login`.
"""

import time

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from items.models import Item
from player_characters.models import Character
from shops.models import Rotation, Shop, ShopStock

CLUB_SLUG = "demo"


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _stock_url(live_server, club_slug, shop_id):
    return f"{live_server.url}{reverse('shops:stock_fragment', args=[club_slug, shop_id])}"


def _wait_for_request(page, requests, stock_url, timeout=7.0):
    """Wait until a request to the stock URL has been seen.

    Uses page.wait_for_timeout so the Playwright event loop pumps request
    callbacks (plain time.sleep would not). wait_for_function itself cannot run
    because the app CSP has no unsafe-eval.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        page.wait_for_timeout(50)
        if any(stock_url in r.url for r in requests):
            return True
    return False


def _console_violations(messages):
    return [
        m
        for m in messages
        if any(
            token in m for token in ("CSP", "EvalError", "unsafe-eval", "Content-Security-Policy")
        )
    ]


@pytest.mark.browser
@pytest.mark.django_db
def test_stock_polls_when_visible(live_server):
    """With the tab visible, the shop fetches /stock/ within 7s with no CSP/eval errors."""
    club = Club.objects.create(name="Demo", slug=CLUB_SLUG)
    user = User.objects.create_user("alice@example.com", password="demo-password")
    membership = Membership.objects.create(user=user, club=club)
    # Exactly one owned character -> auto-selected for this club.
    Character.objects.create(club=club, owner=membership, name="Aria")
    item = Item.objects.create(club=club, name="Rope", value_cp=100)
    shop = Shop.objects.create(club=club, name="General Store")
    Rotation.objects.create(club=club, name="Always", open_date=timezone.localdate()).shops.add(
        shop
    )
    ShopStock.objects.create(shop=shop, item=item, quantity=2)

    session_id = _session_id(user)
    stock_url = _stock_url(live_server, CLUB_SLUG, shop.id)
    shop_url = f"{live_server.url}/c/{club.slug}/shops/{shop.id}/"

    from playwright.sync_api import sync_playwright

    requests = []
    console_messages = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.on("request", lambda req: requests.append(req) if stock_url in req.url else None)
            page.on("console", lambda msg: console_messages.append(msg.text))
            page.goto(shop_url)
            page.wait_for_load_state("networkidle")

            assert _wait_for_request(page, requests, stock_url), (
                f"Expected a stock request to {stock_url} within 7s"
            )

            violations = _console_violations(console_messages)
            assert not violations, f"Console CSP/eval errors: {violations}"
        finally:
            context.close()
            browser.close()
