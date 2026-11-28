"""Browser regression test: the Buy button shows in full at 390 px.

At phone width the Weight column hides (wm-col-optional) so the stock table
does not overflow sideways and the Buy button fits on screen. At desktop
width the Weight column still shows.

Uses Playwright with a real browser; run with ``-m browser``. Excluded from
the default test run. Nothing here weakens the CSP and no inline styles are
added.
"""

import pytest
from django.test import Client

from accounts.models import Club, Membership, User
from player_characters.models import Character
from shops.models import Shop
from shops.seeding import seed_default_general_store

CLUB_SLUG = "demo"


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _make_shop():
    """Seed a club, one player character, and the real General Store from seed_demo.

    The seeded store has long item names, descriptions, bundled stock and
    many rows. That is the data shape that overflowed the table at 390 px.
    """
    club = Club.objects.create(name="Demo", slug=CLUB_SLUG)
    user = User.objects.create_user("alice@example.com", password="demo-password")
    Membership.objects.create(user=user, club=club)
    # Exactly one owned character -> auto-selected for this club.
    Character.objects.create(
        club=club,
        owner=Membership.objects.get(user=user, club=club),
        name="Aria",
    )
    seed_default_general_store(club)
    shop = Shop.objects.get(club=club, name="General Store")
    return club, user, shop


@pytest.mark.browser
@pytest.mark.django_db
def test_buy_button_fits_on_phone(live_server):
    """At 390 px the Buy button is fully on screen with no table scroll."""
    club, user, shop = _make_shop()
    session_id = _session_id(user)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for width in (390, 1280):
                height = 844 if width == 390 else 800
                context = browser.new_context(viewport={"width": width, "height": height})
                context.add_cookies(
                    [{"name": "sessionid", "value": session_id, "url": live_server.url}]
                )
                page = context.new_page()
                page.goto(f"{live_server.url}/c/{club.slug}/shops/{shop.id}/")
                page.wait_for_load_state("networkidle")
                try:
                    if width == 390:
                        result = page.evaluate(
                            "() => {"
                            "const box = document.querySelector('.wm-table-scroll');"
                            "return {sw: box.scrollWidth, cw: box.clientWidth};"
                            "}"
                        )
                        assert result["sw"] <= result["cw"], f"table scrolls: {result}"
                        # Every Buy button: right edge on screen, height >= 44 px.
                        buttons = page.locator("td.actions a.btn")
                        count = buttons.count()
                        assert count > 3, f"expected many Buy buttons, found {count}"
                        for i in range(count):
                            box = buttons.nth(i).bounding_box()
                            assert box is not None, f"Buy button {i} not found"
                            assert box["x"] + box["width"] <= width, (
                                f"Buy button {i} off screen: {box}"
                            )
                            assert box["height"] >= 44, f"Buy button {i} too short: {box}"
                    else:
                        # Desktop: Weight column still shows.
                        assert page.locator('th:has-text("Weight")').is_visible()
                finally:
                    context.close()
        finally:
            browser.close()
