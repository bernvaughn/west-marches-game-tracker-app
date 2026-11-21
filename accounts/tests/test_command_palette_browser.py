"""Browser regression test for the command palette.

Covers:
- The wmCommandPalette Alpine component is registered before Alpine starts
  (Object.keys of the component's data stack is non-empty).
- Ctrl+K opens the palette and lists the side-menu entries.
- Ctrl+G and `/` also open the palette.
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

            # Esc closes the palette.
            page.keyboard.press("Escape")
            _wait_hidden(page, palette)
        finally:
            context.close()
            browser.close()

    assert not errors, f"Unexpected page errors: {errors}"
