"""Browser regression test for the command palette.

Covers:
- The wmCommandPalette Alpine component is registered before Alpine starts
  (Object.keys of the component's data stack is non-empty).
- Ctrl+K opens the palette and lists the side-menu entries.
- Ctrl+G and `/` also open the palette.
- Rows show their text (label and group), search filters rows, a query with
  no match shows "No results", and clicking a row navigates. The vendored
  Alpine is the CSP build, which only evaluates bare names in expressions, so
  these checks catch blank rows and dead search.
- Esc closes the palette.

Run with: uv run pytest -m browser accounts/tests/test_command_palette_browser.py
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


def _blur(page):
    """Move focus off any input so bare-key shortcuts (e.g. "/") are not suppressed."""
    page.evaluate("() => { document.activeElement.blur(); }")


def _press_ctrl(page, key):
    page.keyboard.down("Control")
    page.keyboard.press(key)
    page.keyboard.up("Control")


def _wait_visible(page, palette):
    palette.wait_for(state="visible", timeout=5000)
    assert palette.is_visible()


def _wait_hidden(page, palette):
    palette.wait_for(state="hidden", timeout=5000)
    assert not palette.is_visible()


@pytest.mark.browser
@pytest.mark.django_db
def test_command_palette_opens_lists_entries_and_closes(live_server):
    """Ctrl+K opens the command palette listing menu entries; Esc closes it."""
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

            palette = page.locator(".wm-command-palette")

            # The Alpine component must be registered before Alpine starts.
            data_keys = page.evaluate(
                "Object.keys(document.querySelector('.wm-command-palette')._x_dataStack[0])"
            )
            assert len(data_keys) > 0, "wmCommandPalette was not registered before Alpine started"

            expected_entries = page.locator(".wm-menu-link").count()
            assert expected_entries > 0

            # / opens the palette (page just loaded, nothing focused).
            _blur(page)
            page.keyboard.press("/")
            _wait_visible(page, palette)

            # Esc closes the palette.
            page.keyboard.press("Escape")
            _wait_hidden(page, palette)

            # Ctrl+G opens the palette (works even with an input focused).
            _press_ctrl(page, "KeyG")
            _wait_visible(page, palette)
            page.keyboard.press("Escape")
            _wait_hidden(page, palette)

            # Ctrl+K opens the palette and lists the menu entries.
            _blur(page)
            _press_ctrl(page, "KeyK")
            _wait_visible(page, palette)
            assert page.locator(".wm-command-item").count() == expected_entries

            # Rows are not blank: labels match the side-menu link text.
            menu_labels = [t.strip() for t in page.locator(".wm-menu-link").all_text_contents()]
            row_labels = [
                t.strip() for t in page.locator(".wm-command-item-label").all_text_contents()
            ]
            assert row_labels == menu_labels
            assert all(row_labels)
            assert any(
                t.strip() for t in page.locator(".wm-command-item-group").all_text_contents()
            )

            # Search filters rows.
            page.locator(".wm-command-input").fill("")
            page.locator(".wm-command-input").press_sequentially(menu_labels[0][:3].lower())
            page.wait_for_function(
                "n => document.querySelectorAll('.wm-command-item').length <= n",
                arg=expected_entries - 1 if expected_entries > 1 else 1,
            )
            filtered = page.locator(".wm-command-item").count()
            assert 0 < filtered <= expected_entries
            assert not page.locator(".wm-command-empty").is_visible()

            # A query with no match shows the empty message.
            page.locator(".wm-command-input").fill("")
            page.locator(".wm-command-input").press_sequentially("zzzzqqq")
            page.wait_for_function("document.querySelectorAll('.wm-command-item').length === 0")
            assert page.locator(".wm-command-empty").is_visible()
            assert "zzzzqqq" in page.locator(".wm-command-empty").inner_text()

            # Esc closes the palette.
            page.keyboard.press("Escape")
            _wait_hidden(page, palette)

            # Reopening resets the search; clicking a row navigates to its link.
            _blur(page)
            _press_ctrl(page, "KeyK")
            _wait_visible(page, palette)
            assert page.locator(".wm-command-input").input_value() == ""
            assert page.locator(".wm-command-item").count() == expected_entries
            target = page.locator(".wm-menu-link").nth(1).get_attribute("href")
            with page.expect_navigation():
                page.locator(".wm-command-item").nth(1).click()
            # The link may redirect (e.g. "my character" -> its detail page).
            assert page.url.rstrip("/") != f"{live_server.url}/c/{DEMO_CLUB_SLUG}"
            assert target.startswith(f"/c/{DEMO_CLUB_SLUG}/")
        finally:
            context.close()
            browser.close()

    assert not errors, f"Unexpected page errors: {errors}"
