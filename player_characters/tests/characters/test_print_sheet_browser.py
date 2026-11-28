"""Browser test: the Print sheet button works under the site's CSP.

The button must open the print dialog exactly once per click, and record
last_printed_at. Printing must still happen when the record POST fails.
"""

import pytest
from django.test import Client
from django.urls import reverse

STUB_PRINT = "window.__printCalls = 0; window.print = function () { window.__printCalls += 1; };"


def _session_id(user):
    # Log in before Playwright starts: its event loop blocks sync ORM calls.
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _open_sheet(pw, live_server, session_id, url):
    browser = pw.chromium.launch()
    context = browser.new_context()
    context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
    context.add_init_script(STUB_PRINT)
    page = context.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_server.url + url)
    page.wait_for_load_state("networkidle")
    return browser, page, errors


@pytest.mark.browser
def test_print_sheet_click_prints_once_and_records(
    transactional_db, live_server, club, player, funded
):
    from playwright.sync_api import sync_playwright

    url = reverse("characters:detail", args=[club.slug, funded.pk])
    session_id = _session_id(player)
    with sync_playwright() as pw:
        browser, page, errors = _open_sheet(pw, live_server, session_id, url)
        try:
            with page.expect_response(lambda r: r.request.method == "POST") as resp:
                page.click("[data-print-sheet]")
            assert resp.value.status == 200
            page.wait_for_function("window.__printCalls >= 1")
            page.wait_for_timeout(300)
            assert page.evaluate("window.__printCalls") == 1
            assert errors == []
        finally:
            browser.close()
    funded.refresh_from_db()
    assert funded.last_printed_at is not None


@pytest.mark.browser
def test_print_sheet_prints_when_record_fails(transactional_db, live_server, club, player, funded):
    from playwright.sync_api import sync_playwright

    url = reverse("characters:detail", args=[club.slug, funded.pk])
    session_id = _session_id(player)
    with sync_playwright() as pw:
        browser, page, _errors = _open_sheet(pw, live_server, session_id, url)
        try:

            def fail_post(route):
                if route.request.method == "POST":
                    route.abort()
                else:
                    route.continue_()

            page.route(live_server.url + url, fail_post)
            page.click("[data-print-sheet]")
            page.wait_for_function("window.__printCalls >= 1")
            assert page.evaluate("window.__printCalls") == 1
        finally:
            browser.close()


@pytest.mark.browser
def test_print_card_dropdown_opens_without_console_error(
    transactional_db, live_server, club, player, funded
):
    """The Print card dropdown opens and closes with a clean console.

    Regression test for the Bootstrap tooltip/dropdown instance conflict:
    the toggle used to carry both data-bs-toggle="dropdown" and
    data-wm-tooltip, so Bootstrap refused to bind a second instance on the
    same element and logged an error on every click.
    """
    from playwright.sync_api import expect, sync_playwright

    url = reverse("characters:detail", args=[club.slug, funded.pk])
    session_id = _session_id(player)
    with sync_playwright() as pw:
        browser, page, errors = _open_sheet(pw, live_server, session_id, url)
        try:
            toggle = page.locator('[aria-label="Print card"]').first
            expect(toggle).to_be_visible()

            toggle.click()
            menu = page.locator(".dropdown-menu.show")
            expect(menu).to_be_visible()
            expect(menu.get_by_text("Full page").first).to_be_visible()
            expect(menu.get_by_text("Grid spot").first).to_be_visible()

            toggle.click()
            expect(menu).not_to_be_visible()

            assert errors == []
        finally:
            browser.close()
