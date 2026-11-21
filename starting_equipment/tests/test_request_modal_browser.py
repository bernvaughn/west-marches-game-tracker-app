"""Browser tests for the starting equipment request modal quantity limit.

The quantity limit script lives in static/js/starting_equipment_request.js.
These tests open the request modal in a real browser and check that the
quantity help text never shows "NaN" before an item is chosen, and shows the
correct limit after an item is chosen.

Login uses a server-side session cookie (the login view rate-limits). Waits
use Playwright ``expect`` assertions, which retry without eval, so they work
under the app CSP (no unsafe-eval). Do not use ``page.wait_for_function``.
"""

import pytest
from django.test import Client
from django.urls import reverse
from playwright.sync_api import expect

from items.models import Item
from starting_equipment.models import MagicItemStartingOption


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _request_url(club, character):
    return reverse(
        "starting_equipment:request_new",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


@pytest.fixture
def magic_option_limit_3(template):
    """Magic item starting option with max_per_character=3."""
    item = Item.objects.create(
        club=template.club,
        name="Scroll of Fireball",
        value_cp=10000,
        rarity="rare",
        magic_type="scroll",
    )
    return MagicItemStartingOption.objects.create(
        template=template, item=item, max_per_character=3, notes="Limit 3"
    )


@pytest.fixture
def modal_page(player, character_with_class_bg, magic_option, magic_option_limit_3, live_server):
    """Yield a function that opens the request page in a logged-in browser page."""
    from playwright.sync_api import sync_playwright

    session_id = _session_id(player)
    url = live_server.url + _request_url(character_with_class_bg.club, character_with_class_bg)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        contexts = []

        def open_page():
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            contexts.append(context)
            context.add_cookies(
                [{"name": "sessionid", "value": session_id, "url": live_server.url}]
            )
            page = context.new_page()
            page.goto(url)
            page.wait_for_load_state("networkidle")
            return page

        try:
            yield open_page
        finally:
            for context in contexts:
                context.close()
            browser.close()


@pytest.mark.browser
def test_quantity_help_has_no_nan_on_open(modal_page):
    """Before an item is chosen, no "NaN" in the help text or max attribute."""
    page = modal_page()
    help_text = page.locator("#quantity-help")
    quantity = page.locator("#id_quantity")

    expect(help_text).not_to_contain_text("NaN")
    expect(quantity).not_to_have_attribute("max", "NaN")


@pytest.mark.browser
def test_quantity_help_shows_limit_after_picking_item(modal_page, magic_option_limit_3):
    """After picking an item, the help text shows its max_per_character."""
    page = modal_page()
    item_select = page.locator("#id_item")
    help_text = page.locator("#quantity-help")
    quantity = page.locator("#id_quantity")

    expect(help_text).not_to_contain_text("NaN")

    item_select.select_option(str(magic_option_limit_3.item.pk))

    expect(help_text).to_have_text(
        f"Maximum per character: {magic_option_limit_3.max_per_character}"
    )
    expect(quantity).to_have_attribute("max", str(magic_option_limit_3.max_per_character))
