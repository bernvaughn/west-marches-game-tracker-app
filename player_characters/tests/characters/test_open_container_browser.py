"""Browser test: opening a container pack refreshes the inventory on modal close.

Open Tilda Brightwater's Priest's Pack (``seed_demo`` gives her one), close the
result modal with the X, and assert the pack row is gone and the rolled items
show, all without a page reload.

The same Bootstrap ``hidden.bs.modal`` path handles X, Esc and backdrop closes,
so they are refreshed by the same code path; the X close is the asserted
control per the acceptance criteria.
"""

import time

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from accounts.models import User
from player_characters.models import Character

DEMO_CLUB_SLUG = "demo"
MODAL_CONTENT = "#app-modal .modal-content"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _wait_for(page, expression, timeout=8.0):
    # The app CSP has no unsafe-eval, so page.wait_for_function cannot run.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"Timed out waiting for: {expression}")


@pytest.mark.browser
def test_open_pack_close_x_refreshes_inventory(transactional_db, live_server):
    """Open a pack, close with X, pack row gone and new items show, no reload."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    user = User.objects.get(email="bob@example.com")
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name="Tilda Brightwater")
    session_id = _session_id(user)
    detail_url = reverse(
        "characters:detail", kwargs={"club_slug": DEMO_CLUB_SLUG, "pk": character.pk}
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(live_server.url + detail_url)
            page.wait_for_load_state("networkidle")

            # The sheet lists Priest's Pack with an Open button.
            pack_row = page.locator('tr:has-text("Priest\'s Pack")')
            pack_row.wait_for()
            pack_row.locator('button:has-text("Open")').click()

            # The result modal opens and reveals the contents.
            page.wait_for_selector(MODAL_CONTENT, state="visible", timeout=5000)

            # Close with the X.
            page.locator(MODAL_CONTENT + " .btn-close").click()
            page.wait_for_selector(MODAL_CONTENT, state="hidden", timeout=5000)

            # The inventory behind the modal refreshed: pack gone, new items show.
            inventory = 'document.querySelector("#sheet-inventory")'
            _wait_for(
                page,
                f"{inventory} && {inventory}.textContent.includes('Backpack')",
            )
            assert "Priest's Pack" not in page.evaluate(f"{inventory}.textContent")
            assert page.evaluate(f"{inventory}.textContent.includes('Backpack')")
        finally:
            browser.close()
