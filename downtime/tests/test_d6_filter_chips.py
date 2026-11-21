"""Regression test: filter chips show a selected state and survive a reload.

The filter chips (#downtime-filters) post via HTMX and swap only #downtime-jobs,
so the server-rendered wm-filter-chip--active class never reaches the chips after
a filter click. The chips now style their checked state with
.wm-filter-chip:has(input:checked) and the form pushes the URL (hx-push-url),
so a reload keeps both the accent look and the filtered list.
"""

import pytest
from django.core.management import call_command

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    from django.test import Client

    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _chip_style(page):
    """Return the computed background/border/color of the cost "2" chip label."""
    return page.evaluate(
        """() => {
        const chip = Array.from(document.querySelectorAll('#downtime-filters .wm-filter-chip'))
          .find(el => el.textContent.trim() === '2');
        if (!chip) return null;
        const s = getComputedStyle(chip);
        return { background: s.backgroundColor, border: s.borderColor, color: s.color };
      }"""
    )


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_filter_chip_shows_active_state_and_survives_reload(transactional_db, live_server, width):
    """Clicking a cost chip styles it active, pushes the URL, and survives reload."""
    from playwright.sync_api import sync_playwright

    from accounts.models import User

    _seed_demo()
    user = User.objects.get(email=DEMO_PLAYER_EMAIL)
    session_id = _session_id(user)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/downtime/")
            page.wait_for_load_state("networkidle")

            # Click the cost "2" chip.
            page.locator('#downtime-filters .wm-filter-chip:has-text("2")').click()

            # The list narrows and the URL carries the filter.
            page.wait_for_url("**/c/demo/downtime/?cost=2")
            page.wait_for_selector("text=No jobs match your filters.", state="visible")

            # The chip shows the accent look.
            style = _chip_style(page)
            assert style is not None
            assert style["background"] == "rgb(184, 50, 46)", style

            # Reload keeps the chip active and the list filtered.
            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_url("**/c/demo/downtime/?cost=2")
            page.wait_for_selector("text=No jobs match your filters.", state="visible")
            style = _chip_style(page)
            assert style is not None
            assert style["background"] == "rgb(184, 50, 46)", style
        finally:
            browser.close()
