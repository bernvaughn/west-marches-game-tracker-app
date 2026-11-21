"""Browser test: Replay button in container open modal has button styling and works."""

import time

import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User
from items.models import Item
from items.tests.factories import add_slot, make_container
from ledger.services import Line, record
from player_characters.models import Character

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"
MODAL = "#app-modal .modal-content"
OPEN_RESULT = "[data-wm-open-result]"
REPLAY_BTN = "[data-wm-replay]"


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


def _award(character, item, quantity=1, actor=None):
    return record(character, "award", [Line(item=item, quantity=quantity)], actor=actor)


def _fixed_container(club, name="Pack", item_name="Rope"):
    container = make_container(club, name=name)
    item = Item.objects.create(club=club, name=item_name, value_cp=1)
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100)
    return container, item


def _wait_for_reveal_complete(page):
    """Wait for the reveal animation to complete (wm-reveal--armed removed)."""
    _wait_for(
        page,
        f'document.querySelector("{OPEN_RESULT}") && '
        f'!document.querySelector("{OPEN_RESULT}").classList.contains("wm-reveal--armed")',
    )


def _wait_for_replay_button(page):
    """Wait for the Replay button to be added to the DOM."""
    _wait_for(
        page,
        f'document.querySelector("{REPLAY_BTN}") !== null',
    )


def _armed_expr():
    """Expression to check if reveal is armed (animation running)."""
    return (
        f'document.querySelector("{OPEN_RESULT}") && '
        f'document.querySelector("{OPEN_RESULT}").classList.contains("wm-reveal--armed")'
    )


@pytest.mark.browser
def test_container_open_replay_button_has_styling_and_works(transactional_db, live_server):
    """Replay button in container open modal has btn classes and replays the reveal."""
    from playwright.sync_api import sync_playwright

    _seed_demo()

    # Create a container pack and award it to a character
    club = Character.objects.first().club
    user = User.objects.get(email=DEMO_PLAYER_EMAIL)
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name__startswith="Aria")

    container, rope = _fixed_container(club, name="Explorer's Pack", item_name="Rope")
    _award(character, container, actor=user)

    session_id = _session_id(user)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/characters/{character.pk}/")
            page.wait_for_load_state("networkidle")

            # Click "Open" on the pack
            page.locator(f'tr:has(td:has-text("{container.name}")) button:has-text("Open")').click()

            # Wait for modal to open
            page.wait_for_selector(MODAL, state="visible", timeout=5000)

            # Wait for Replay button to appear (added by JS after modal shown)
            _wait_for_replay_button(page)

            # Wait for the reveal animation to complete
            _wait_for_reveal_complete(page)

            # Assert Replay button has btn class and non-default border radius
            replay_btn = page.locator(REPLAY_BTN)
            assert replay_btn.count() == 1

            # Check it has the btn class (bootstrap button base class)
            assert "btn" in (replay_btn.get_attribute("class") or "")

            # Check computed border-radius is not 0px (default button has no border-radius)
            border_radius = replay_btn.evaluate("el => getComputedStyle(el).borderTopLeftRadius")
            assert border_radius != "0px", f"Expected non-zero border radius, got {border_radius}"

            # Click Replay and assert reveal plays again
            replay_btn.click()

            # Wait for animation to start (armed class added)
            _wait_for(page, _armed_expr())

            # Wait for animation to complete again
            _wait_for_reveal_complete(page)

            # Verify items are visible (opacity 1)
            visible_count = page.evaluate(
                f'document.querySelectorAll("{OPEN_RESULT} [data-wm-reveal-item]").length'
            )
            assert visible_count > 0, "Items should exist in the reveal"

        finally:
            browser.close()


@pytest.mark.browser
def test_container_open_replay_button_at_mobile_width(transactional_db, live_server):
    """Replay button styling also works at 390px width (mobile)."""
    from playwright.sync_api import sync_playwright

    _seed_demo()

    club = Character.objects.first().club
    user = User.objects.get(email=DEMO_PLAYER_EMAIL)
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name__startswith="Aria")

    container, rope = _fixed_container(club, name="Explorer's Pack", item_name="Rope")
    _award(character, container, actor=user)

    session_id = _session_id(user)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/characters/{character.pk}/")
            page.wait_for_load_state("networkidle")

            # Click "Open" on the pack
            page.locator(f'tr:has(td:has-text("{container.name}")) button:has-text("Open")').click()

            page.wait_for_selector(MODAL, state="visible", timeout=5000)

            # Wait for Replay button to appear
            _wait_for_replay_button(page)

            _wait_for_reveal_complete(page)

            replay_btn = page.locator(REPLAY_BTN)
            assert replay_btn.count() == 1

            # Check it has the btn class
            assert "btn" in (replay_btn.get_attribute("class") or "")

            # Check computed border-radius is not 0px
            border_radius = replay_btn.evaluate("el => getComputedStyle(el).borderTopLeftRadius")
            assert border_radius != "0px", f"Expected non-zero border radius, got {border_radius}"

            # Click Replay and assert reveal plays again
            replay_btn.click()

            _wait_for(page, _armed_expr())
            _wait_for_reveal_complete(page)

            visible_count = page.evaluate(
                f'document.querySelectorAll("{OPEN_RESULT} [data-wm-reveal-item]").length'
            )
            assert visible_count > 0, "Items should exist in the reveal at mobile width"

        finally:
            browser.close()
