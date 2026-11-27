"""Browser test: contact email saved alert shows the stored address.

The success alert after saving the contact email must show the expanded
address, not the raw Django template braces. Regression test for
mail/templates/mail/_club_contact_card.html.
"""

import time

import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User

DEMO_CLUB_SLUG = "demo"
DEMO_ADMIN_EMAIL = "gm@example.com"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(email):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    user = User.objects.get(email=email)
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
def test_contact_email_saved_alert_expands_address(transactional_db, live_server, width):
    """Saving the contact email shows an alert with the address expanded, not braces."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    session_id = _session_id(DEMO_ADMIN_EMAIL)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(
                f"{live_server.url}/c/{DEMO_CLUB_SLUG}/accounts/settings/",
                wait_until="networkidle",
            )

            # Fill in the contact email input.
            page.fill('input[name="contact_email"]', "guild-contact@example.com")

            # Click Save in the Contact email card (the form that holds the contact_email input).
            page.locator('form:has(input[name="contact_email"]) button[type="submit"]').click()

            # Wait for the success alert to appear (HTMX swaps the card).
            _wait_for(page, "document.querySelector('.wm-alert--success')")

            # The alert text must show the expanded address, not braces.
            alert = page.locator(".wm-alert--success").text_content()
            assert "Contact email saved" in alert
            assert "{{" not in alert, "template braces were not expanded in the alert"
            assert "guild-contact@example.com" in alert
            assert "The contact email is now guild-contact@example.com." in alert

            # Reload and check the input value is kept.
            page.reload()
            page.wait_for_load_state("networkidle")
            input_value = page.locator('input[name="contact_email"]').input_value()
            assert input_value == "guild-contact@example.com"

        finally:
            browser.close()
