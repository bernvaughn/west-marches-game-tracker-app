"""Browser regression test for bulk approve: the queue reloads and a toast shows.

Covers the fault where clicking "Approve all" in the bulk approve modal returned
204, closed the modal, but never reloaded the queue or showed a message, so the
rows kept reading "Requested" with their checkboxes.

Login uses a server-side session cookie. Waits use Playwright ``expect``
assertions, which work under the app CSP (no unsafe-eval). Do not use
``page.wait_for_function``.

Run with: pytest -m browser map/tests/test_bulk_approve_browser.py
"""

import pytest
from django.test import Client
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from map.models import MapRequest, TileVisit

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def visible_location(tile_location, hex_map, character, other_character):
    """A discovered location the player can request credit for."""
    from map.services import add_to_credit

    add_to_credit(tile_location, "discovered", [other_character])
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    return tile_location


@pytest.fixture
def bulk_approve_page(club, game_master, player, character, visible_location, live_server):
    """Yield the queue page as the game master, with two requested credit requests."""
    client = Client()
    client.force_login(player)
    client.post(
        reverse("map:request_credit", args=[club.slug, "discovered", visible_location.pk]),
        {"characters": [character.pk], "date": "2026-01-02", "note": "d"},
    )
    client.post(
        reverse("map:request_credit", args=[club.slug, "discovered", visible_location.pk]),
        {"characters": [character.pk], "date": "2026-01-03", "note": "e"},
    )
    assert MapRequest.objects.filter(status="requested").count() == 2

    gm_client = Client()
    gm_client.force_login(game_master)
    session_id = gm_client.cookies["sessionid"].value

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        page.goto(f"{live_server.url}/c/{club.slug}/map/requests/")
        page.wait_for_load_state("networkidle")
        try:
            yield page
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("width", [1280, 390])
def test_bulk_approve_reloads_queue_and_shows_toast(bulk_approve_page, width):
    page = bulk_approve_page
    page.set_viewport_size({"width": width, "height": 800})

    # Two requested rows with checkboxes.
    expect(page.locator('input[name="requests"]')).to_have_count(2)

    # Select all requests and open the bulk approve modal.
    page.locator("#bulk-select-all").check()
    page.locator("#bulk-approve-btn").click()
    modal = page.locator("#app-modal")
    expect(modal).to_be_visible()

    # Approve all: the response carries HX-Refresh, so the queue reloads.
    modal.get_by_role("button", name="Approve all").click()
    page.wait_for_load_state("networkidle")

    # The modal closed, no checkboxes remain, and every row shows "Approved".
    expect(modal).to_be_hidden()
    expect(page.locator('input[name="requests"]')).to_have_count(0)
    expect(page.locator(".wm-badge--success")).to_have_count(4)

    # A success toast is visible after the reload.
    expect(page.locator(".wm-toast")).to_be_visible()
