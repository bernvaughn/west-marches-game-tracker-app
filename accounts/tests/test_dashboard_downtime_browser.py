"""Browser regression test for the dashboard Downtime result modal.

Covers:
- The wheel spins in the dashboard result modal (downtime_wheel.js is loaded on
  the dashboard).
- "Close & Refresh" uses a valid CSS target (#dashboard-card-downtime) instead of
  the invalid `:contains()` selector, so the Downtime card reloads and its badge
  shows the new balance after a spend.
- No page errors are raised while clicking through the flow.

Run with: uv run pytest -m browser accounts/tests/test_dashboard_downtime_browser.py
"""

import pytest
from playwright.sync_api import sync_playwright

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"
DEMO_PASSWORD = "demo-password"


def _seed_demo():
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)


def _login(page, live_server):
    page.goto(f"{live_server.url}/accounts/login/")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="username"]', DEMO_PLAYER_EMAIL)
    page.fill('input[name="password"]', DEMO_PASSWORD)
    page.click("form button[type=submit], form input[type=submit]")
    page.wait_for_load_state("networkidle")


@pytest.mark.browser
@pytest.mark.django_db
def test_dashboard_downtime_spend_reloads_card_and_wheel_spins(live_server):
    """Spending downtime from the dashboard reloads the card and spins the wheel."""
    _seed_demo()

    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("pageerror", lambda err: errors.append(str(err)))
        try:
            _login(page, live_server)

            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/")
            page.wait_for_load_state("networkidle")

            # Downtime card: Aria starts with 2 points from seed_demo.
            page.wait_for_selector("#dashboard-card-downtime", timeout=5000)
            card = page.locator("#dashboard-card-downtime")
            assert card.locator(".badge").inner_text() == "2"

            # Spend one point on "Work at a bakery" -> confirm modal opens.
            card.locator('button:has-text("Spend")').click()
            page.wait_for_selector("#app-modal .modal-content form", timeout=5000)
            page.locator("#app-modal .modal-content button:has-text('Take the job')").click()

            # Result modal opens and the wheel starts (data-started is set).
            page.wait_for_selector("[data-downtime-wheel][data-started]", timeout=5000)

            # Close & Refresh: modal closes and the Downtime card reloads with the new balance.
            page.locator("#app-modal .modal-content button:has-text('Close & Refresh')").click()
            page.wait_for_selector("#dashboard-card-downtime .badge:has-text('1')", timeout=5000)
            assert card.locator(".badge").inner_text() == "1"
        finally:
            context.close()
            browser.close()

    assert not errors, f"Unexpected page errors: {errors}"
