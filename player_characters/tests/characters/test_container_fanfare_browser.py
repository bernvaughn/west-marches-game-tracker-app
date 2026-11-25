"""Browser tests for the container fanfare animation (S2).

- Animation finishes with every icon in the row (1280px and 390px viewports).
- Replay does not POST to the server.
- Sound toggle persists across reloads.
"""

import time

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from accounts.models import User
from items.models import Item
from items.tests.factories import add_slot, make_container
from ledger.services import Line, record
from player_characters.models import Character

DEMO_CLUB_SLUG = "demo"
MODAL_CONTENT = "#app-modal .modal-content"
FANFARE_CONTAINER = "[data-fanfare]"
REVEAL_ITEMS = "[data-wm-reveal-item]"
REPLAY_BUTTON = "[data-wm-fanfare-replay]"
SOUND_TOGGLE = "[data-wm-fanfare-sound]"
LIVE_REGION = "[data-wm-live]"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _wait_for(page, expression, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"Timed out waiting for: {expression}")


@pytest.mark.browser
@pytest.mark.parametrize(
    "viewport", [{"width": 1280, "height": 800}, {"width": 390, "height": 844}]
)
def test_fanfare_animation_finishes_with_all_items(viewport, transactional_db, live_server):
    """Fanfare animation completes and all item icons end up in the row."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    user = User.objects.get(email="bob@example.com")
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name="Tilda Brightwater")
    session_id = _session_id(user)

    # Ensure the character has a pack to open
    container = make_container(character.club, "Test Pack")
    container.symbol = "🎁"
    container.save()
    sword = Item.objects.create(club=character.club, name="Sword", symbol="⚔️", value_cp=100)
    shield = Item.objects.create(club=character.club, name="Shield", symbol="🛡️", value_cp=80)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)
    add_slot(container, [(shield, 1, 1, 1)], chance_pct=100)
    record(character, "award", [Line(item=container, quantity=1)], actor=character.owner.user)

    detail_url = reverse(
        "characters:detail", kwargs={"club_slug": DEMO_CLUB_SLUG, "pk": character.pk}
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport=viewport)
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(live_server.url + detail_url)
            page.wait_for_load_state("networkidle")

            # Open the pack
            pack_row = page.locator('tr:has-text("Test Pack")')
            pack_row.wait_for()
            pack_row.locator('button:has-text("Open")').click()

            # Wait for modal to open
            page.wait_for_selector(MODAL_CONTENT, state="visible", timeout=5000)

            # Wait for fanfare container to be present
            fanfare = page.locator(FANFARE_CONTAINER)
            fanfare.wait_for(timeout=5000)

            # Wait for animation to complete: items should be visible in the reveal row
            # The reveal items are initially hidden during animation, then shown
            _wait_for(
                page,
                f'document.querySelectorAll("{REVEAL_ITEMS}").length === 2 '
                f'&& Array.from(document.querySelectorAll("{REVEAL_ITEMS}"))'
                f'.every(el => getComputedStyle(el).opacity === "1" '
                f'&& getComputedStyle(el).transform === "none")',
            )

            # Verify both items are in the row with correct content
            items = page.locator(REVEAL_ITEMS)
            assert items.count() == 2
            assert "⚔️" in items.nth(0).text_content()
            assert "Sword" in items.nth(0).text_content()
            assert "🛡️" in items.nth(1).text_content()
            assert "Shield" in items.nth(1).text_content()

            # Live region should be populated
            live = page.locator(LIVE_REGION)
            _wait_for(page, f'document.querySelector("{LIVE_REGION}").textContent.length > 0')
            assert "Sword" in live.text_content()
            assert "Shield" in live.text_content()

        finally:
            browser.close()


@pytest.mark.browser
def test_fanfare_replay_does_not_post(transactional_db, live_server):
    """Replay button replays animation without posting to the server."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    user = User.objects.get(email="bob@example.com")
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name="Tilda Brightwater")
    session_id = _session_id(user)

    container = make_container(character.club, "Test Pack")
    container.symbol = "🎁"
    container.save()
    sword = Item.objects.create(club=character.club, name="Sword", symbol="⚔️", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)
    record(character, "award", [Line(item=container, quantity=1)], actor=character.owner.user)

    detail_url = reverse(
        "characters:detail", kwargs={"club_slug": DEMO_CLUB_SLUG, "pk": character.pk}
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()

        # Track network requests
        post_requests = []
        page.on("request", lambda req: post_requests.append(req) if req.method == "POST" else None)

        try:
            page.goto(live_server.url + detail_url)
            page.wait_for_load_state("networkidle")

            pack_row = page.locator('tr:has-text("Test Pack")')
            pack_row.wait_for()
            pack_row.locator('button:has-text("Open")').click()

            page.wait_for_selector(MODAL_CONTENT, state="visible", timeout=5000)

            # Wait for initial animation to complete
            _wait_for(
                page,
                f'document.querySelectorAll("{REVEAL_ITEMS}").length === 1 && '
                f'getComputedStyle(document.querySelector("{REVEAL_ITEMS}")).opacity === "1"',
            )

            # Clear any requests made during initial load/animation
            post_requests.clear()

            # Click Replay
            replay_btn = page.locator(REPLAY_BUTTON)
            replay_btn.wait_for(timeout=5000)
            replay_btn.click()

            # Wait for replay animation to complete
            _wait_for(
                page,
                f'getComputedStyle(document.querySelector("{REVEAL_ITEMS}")).opacity === "1"',
            )

            # Assert no POST requests were made during replay
            assert len(post_requests) == 0, f"Replay made {len(post_requests)} POST request(s)"

        finally:
            browser.close()


@pytest.mark.browser
def test_fanfare_sound_toggle_persists_across_reloads(transactional_db, live_server):
    """Sound toggle state is saved in localStorage and persists across page reloads."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    user = User.objects.get(email="bob@example.com")
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name="Tilda Brightwater")
    session_id = _session_id(user)

    container = make_container(character.club, "Test Pack")
    container.symbol = "🎁"
    container.save()
    sword = Item.objects.create(club=character.club, name="Sword", symbol="⚔️", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)
    record(character, "award", [Line(item=container, quantity=1)], actor=character.owner.user)

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

            pack_row = page.locator('tr:has-text("Test Pack")')
            pack_row.wait_for()
            pack_row.locator('button:has-text("Open")').click()

            page.wait_for_selector(MODAL_CONTENT, state="visible", timeout=5000)

            # Wait for fanfare to initialize
            sound_toggle = page.locator(SOUND_TOGGLE)
            sound_toggle.wait_for(timeout=5000)

            # Initial state should be off (🔇)
            assert sound_toggle.text_content().strip() == "🔇"
            assert sound_toggle.get_attribute("aria-pressed") == "false"

            # Verify localStorage is initially off
            sound_state = page.evaluate("localStorage.getItem('containerFanfareSound')")
            assert sound_state == "off"

            # Click to enable sound
            sound_toggle.click()

            # Verify UI updated
            assert sound_toggle.text_content().strip() == "🔊"
            assert sound_toggle.get_attribute("aria-pressed") == "true"

            # Verify localStorage updated
            sound_state = page.evaluate("localStorage.getItem('containerFanfareSound')")
            assert sound_state == "on"

            # Reload the page
            page.reload()
            page.wait_for_load_state("networkidle")

            # Open the pack again
            pack_row = page.locator('tr:has-text("Test Pack")')
            pack_row.wait_for()
            pack_row.locator('button:has-text("Open")').click()

            page.wait_for_selector(MODAL_CONTENT, state="visible", timeout=5000)

            # Wait for fanfare to initialize
            sound_toggle = page.locator(SOUND_TOGGLE)
            sound_toggle.wait_for(timeout=5000)

            # Sound should still be on after reload
            assert sound_toggle.text_content().strip() == "🔊"
            assert sound_toggle.get_attribute("aria-pressed") == "true"

            sound_state = page.evaluate("localStorage.getItem('containerFanfareSound')")
            assert sound_state == "on"

        finally:
            browser.close()


@pytest.mark.browser
def test_fanfare_empty_result_shows_message_no_animation(transactional_db, live_server):
    """Empty result shows friendly message with no animation."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    user = User.objects.get(email="bob@example.com")
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name="Tilda Brightwater")
    session_id = _session_id(user)

    # Create a container with a slot that will always miss (50% chance,
    # we'll use a seeded RNG via test)
    # For browser test, we create a container and use the
    # AlwaysMissRNG approach via direct view call
    # Actually, let's just open a container that has no slots
    container = make_container(character.club, "Empty Box")
    container.symbol = "📦"
    container.save()
    # No slots added = always empty
    record(character, "award", [Line(item=container, quantity=1)], actor=character.owner.user)

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

            pack_row = page.locator('tr:has-text("Empty Box")')
            pack_row.wait_for()
            pack_row.locator('button:has-text("Open")').click()

            page.wait_for_selector(MODAL_CONTENT, state="visible", timeout=5000)

            # Check for empty message
            content = page.locator(MODAL_CONTENT)
            assert "Nothing was inside." in content.text_content()

            # No reveal items should exist
            reveal_items = page.locator(REVEAL_ITEMS)
            assert reveal_items.count() == 0

            # No replay button for empty result
            replay_btn = page.locator(REPLAY_BUTTON)
            assert replay_btn.count() == 0

            # No sound toggle for empty result
            sound_toggle = page.locator(SOUND_TOGGLE)
            assert sound_toggle.count() == 0

        finally:
            browser.close()
