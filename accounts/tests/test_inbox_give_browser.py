"""Browser regression test for the inbox Give flow (flow 7).

Covers:
- A single coins grant: Review summary names the character and amount,
  Back returns to the form keeping the values, Review again, Give grants,
  the modal closes and the Granted list shows the grant.
- Batch **Back** returns to the form showing "Batch: 2 grants".
- A map-only batch confirms and shows a Granted entry.

Run with: uv run pytest -m browser accounts/tests/test_inbox_give_browser.py
"""

import time

import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User

DEMO_CLUB_SLUG = "demo"
DEMO_GM_EMAIL = "gm@example.com"
DEMO_PASSWORD = "demo-password"
MODAL = "#app-modal .modal-content"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _wait_for(page, expression, timeout=5.0):
    # The app CSP has no unsafe-eval, so page.wait_for_function cannot run.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"Timed out waiting for: {expression}")


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_inbox_give_flow_review_back_give_shows_granted(transactional_db, live_server, width):
    """A single coins grant can go Review, Back, Review, Give and lands in Granted."""
    _seed_demo()
    user = User.objects.get(email=DEMO_GM_EMAIL)
    session_id = _session_id(user)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies(
            [{"name": "sessionid", "value": session_id, "url": live_server.url}]
        )
        page = context.new_page()
        try:
            page.goto(
                f"{live_server.url}/c/{DEMO_CLUB_SLUG}/accounts/messages/?status=all"
            )
            page.wait_for_load_state("networkidle")

            # Open Give coins on Alice's message.
            page.locator('[aria-label="Give coins"]').click()
            page.wait_for_selector(MODAL, state="visible", timeout=5000)

            # Fill 5 gp.
            page.locator('input[name="coins_gp"]').fill("5")

            # Review -> summary names Aria Windrunner and 5 gp.
            page.locator('button:has-text("Review")').click()
            page.wait_for_selector(':has-text("Aria Windrunner")', timeout=5000)
            page.wait_for_selector(':has-text("5 gp")', timeout=5000)

            # Back -> returns to the form keeping the 5 gp.
            page.locator('button:has-text("Back")').click()
            page.wait_for_selector('input[name="coins_gp"]', state="visible", timeout=5000)
            assert page.locator('input[name="coins_gp"]').input_value() == "5"

            # Review again.
            page.locator('button:has-text("Review")').click()
            page.wait_for_selector(':has-text("Aria Windrunner")', timeout=5000)
            page.wait_for_selector(':has-text("5 gp")', timeout=5000)

            # Give -> modal closes.
            page.locator('button:has-text("Give")').click()
            page.wait_for_selector(MODAL, state="hidden", timeout=5000)
            page.wait_for_timeout(2000)

            # The inbox list reloads (inboxChanged) once the modal closes.
            page.wait_for_selector('.wm-granted:has-text("Aria Windrunner")', timeout=10000)
            granted = page.locator(".wm-granted").filter(has_text="Aria Windrunner")
            assert granted.count() >= 1
            assert "5 gp" in granted.first.inner_text()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_inbox_give_batch_back_returns_to_form(transactional_db, live_server, width):
    """Batch Back returns to the form showing 'Batch: 2 grants' (no loop)."""
    _seed_demo()
    user = User.objects.get(email=DEMO_GM_EMAIL)
    session_id = _session_id(user)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies(
            [{"name": "sessionid", "value": session_id, "url": live_server.url}]
        )
        page = context.new_page()
        try:
            page.goto(
                f"{live_server.url}/c/{DEMO_CLUB_SLUG}/accounts/messages/?status=all"
            )
            page.wait_for_load_state("networkidle")

            # Batch: add two coins grants.
            page.locator('[aria-label="Give coins"]').click()
            page.wait_for_selector(MODAL, state="visible", timeout=5000)
            page.locator('input[name="coins_gp"]').fill("10")
            page.locator('button:has-text("Add another item/coin")').click()
            page.wait_for_selector('text="Batch: 1 grant"', timeout=5000)
            page.locator('input[name="coins_gp"]').fill("5")
            page.locator('button:has-text("Add another item/coin")').click()
            page.wait_for_selector('text="Batch: 2 grants"', timeout=5000)

            # Review Batch.
            page.locator('button:has-text("Review Batch")').click()
            page.wait_for_selector('text="Batch Grant Summary"', timeout=5000)

            # Back -> returns to the form showing "Batch: 2 grants".
            page.locator('button:has-text("Back")').click()
            page.wait_for_selector('text="Batch: 2 grants"', timeout=5000)
            assert page.locator('text="Batch: 2 grants"').count() >= 1
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_inbox_give_map_only_batch_grants(transactional_db, live_server, width):
    """A map-only batch confirms and shows a Granted entry."""
    _seed_demo()
    user = User.objects.get(email=DEMO_GM_EMAIL)
    session_id = _session_id(user)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies(
            [{"name": "sessionid", "value": session_id, "url": live_server.url}]
        )
        page = context.new_page()
        try:
            page.goto(
                f"{live_server.url}/c/{DEMO_CLUB_SLUG}/accounts/messages/?status=all"
            )
            page.wait_for_load_state("networkidle")

            js_errors = []
            page.on("pageerror", lambda err: js_errors.append(str(err)))
            page.on("console", lambda msg: js_errors.append(msg.text) if msg.type == "error" else None)

            # Map-only batch: pick Discovered and a location, add to batch, confirm.
            # The map_kind radios are rendered as labels; click the Discovered label.
            page.locator('[aria-label="Give map credit"]').click()
            page.wait_for_selector(MODAL, state="visible", timeout=5000)
            page.locator('label[for="id_map_kind_1"]').click()
            page.locator('select[name="location"]').select_option(index=1)
            page.locator('button:has-text("Add another item/coin")').click()
            page.wait_for_selector('text="Batch: 1 grant"', timeout=5000)
            page.locator('button:has-text("Review Batch")').click()
            page.wait_for_selector('text="Batch Grant Summary"', timeout=5000)
            page.locator('button:has-text("Give")').click()
            page.wait_for_selector(MODAL, state="hidden", timeout=5000)
            page.wait_for_timeout(2000)

            # The inbox list reloads (inboxChanged) once the modal closes.
            page.wait_for_selector('.wm-granted:has-text("Discovered")', timeout=10000)
            granted = page.locator(".wm-granted").filter(has_text="Discovered")
            assert granted.count() >= 1, f"JS errors: {js_errors}"
        finally:
            browser.close()
