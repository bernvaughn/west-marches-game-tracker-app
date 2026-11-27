"""Browser regression test for the item picker in the Give items inbox modal.

Covers:
- Typing in the picker search box narrows the result list (the search input
  has name="q" so htmx sends the query).
- A picked item survives the modal form POST (the noscript select fallback is
  removed by JS so only one items-0-item value is submitted).
- The granted item appears under "Granted" in the inbox after the grant is
  confirmed.

Run with: uv run pytest -m browser accounts/tests/test_inbox_give_items_browser.py
"""

import pytest
from playwright.sync.api import expect, sync_playwright


def _seed_items():
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)


def _login(page, live_server):
    """Log in as the demo club admin via the login page."""
    page.goto(f"{live_server.url}/accounts/login/")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="username"]', "alice@example.com")
    page.fill('input[name="password"]', "demo-password")
    page.click("form button[type=submit], form input[type=submit]")
    page.wait_for_load_state("networkidle")


@pytest.mark.browser
@pytest.mark.django_db
def test_item_picker_search_and_grant(live_server):
    """Open Give items, search, pick an item, grant it, see it under Granted."""
    _seed_items()

    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("pageerror", lambda err: errors.append(str(err)))
        try:
            _login(page, live_server)

            # Open the inbox. The demo seed creates a player message.
            page.goto(f"{live_server.url}/c/demo/accounts/messages/")
            page.wait_for_load_state("networkidle")

            # Open the Give items modal from the first open message row.
            page.locator('a[aria-label="Give items"]').first.click()
            page.wait_for_selector("#app-modal .modal-content", timeout=5000)

            # The search input must have name="q" so htmx sends the query.
            search = page.locator("#app-modal input[type='search'][name='q']")
            expect(search).to_have_attribute("name", "q")

            # Type a search term and verify results narrow.
            search.fill("Longsword")
            page.wait_for_timeout(300)  # allow htmx debounce

            results = page.locator("#app-modal .wm-item-picker-result")
            expect(results.first).to_be_visible()
            result_names = results.locator(".fw-medium").all_text_contents()
            assert all("Longsword" in n for n in result_names), (
                f"Expected only Longsword results, got: {result_names}"
            )

            # Pick the first result.
            results.first.click()

            # Fill quantity and submit the row.
            page.locator("#app-modal input[name$='-quantity']").fill("1")
            page.locator("#app-modal button:has-text('Add another item/coin')").click()
            page.wait_for_timeout(300)

            # Review the batch and confirm.
            page.locator("#app-modal button:has-text('Review Batch')").click()
            page.wait_for_selector(
                "#app-modal .modal-content button:has-text('Confirm')", timeout=5000
            )
            page.locator("#app-modal .modal-content button:has-text('Confirm')").click()
            page.wait_for_load_state("networkidle")

            # Back in the inbox, the granted item should appear under Granted.
            page.wait_for_selector(".wm-granted", timeout=5000)
            granted = page.locator(".wm-granted").text_content()
            assert "Longsword" in granted, f"Expected Longsword under Granted, got: {granted}"
        finally:
            context.close()
            browser.close()

    assert not errors, f"Unexpected page errors: {errors}"
