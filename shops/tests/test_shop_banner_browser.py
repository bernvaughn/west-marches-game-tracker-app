"""Browser tests for shop banner toggles (keeper bio and shop description)."""

import pytest

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"
DEMO_PASSWORD = "demo-password"


def _seed_demo():
    """Seed the demo data for browser tests."""
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)
    from scripts.screenshot_pages import extra_fixtures

    extra_fixtures()


def _shop_detail_url(live_server, shop_id=2):
    return f"{live_server.url}/c/{DEMO_CLUB_SLUG}/shops/{shop_id}/"  # The Rusty Lantern is ID 2


def _login_url(live_server):
    return f"{live_server.url}/accounts/login/"


def _login_page(page, live_server):
    """Log in as demo player."""
    page.goto(_login_url(live_server))
    page.fill("input[name=username]", DEMO_PLAYER_EMAIL)
    page.fill("input[name=password]", DEMO_PASSWORD)
    page.click("form button[type=submit], form input[type=submit]")
    page.wait_for_load_state("networkidle")


@pytest.mark.browser
@pytest.mark.django_db
def test_keeper_toggle_opens_and_closes_bio(live_server):
    """Clicking the keeper name opens the bio; second click closes it."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            _login_page(page, live_server)

            # Go to shop detail page (The Rusty Lantern, keeper Old Marta)
            page.goto(_shop_detail_url(live_server))
            page.wait_for_load_state("networkidle")

            # Find keeper toggle button
            keeper_toggle = page.query_selector(".wm-shop-keeper-toggle")
            assert keeper_toggle, "Keeper toggle button not found"

            # Initially closed: aria-expanded=false, box hidden
            assert keeper_toggle.get_attribute("aria-expanded") == "false"
            keeper_box = page.query_selector("#keeper-about")
            assert keeper_box, "Keeper bio box not found"
            assert keeper_box.is_hidden()

            # Click keeper toggle - should open
            keeper_toggle.click()
            page.wait_for_timeout(100)  # allow JS to run

            assert keeper_toggle.get_attribute("aria-expanded") == "true"
            assert not keeper_box.is_hidden()
            assert "flour-dusted" in keeper_box.inner_text()

            # Click again - should close
            keeper_toggle.click()
            page.wait_for_timeout(100)

            assert keeper_toggle.get_attribute("aria-expanded") == "false"
            assert keeper_box.is_hidden()

        finally:
            context.close()
            browser.close()


@pytest.mark.browser
@pytest.mark.django_db
def test_description_toggle_opens_and_closes(live_server):
    """Clicking the description icon opens the description; second click closes it."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            _login_page(page, live_server)

            page.goto(_shop_detail_url(live_server))
            page.wait_for_load_state("networkidle")

            # Find description toggle button
            desc_toggle = page.query_selector(".wm-shop-about-toggle")
            assert desc_toggle, "Description toggle button not found"

            # Initially closed
            assert desc_toggle.get_attribute("aria-expanded") == "false"
            desc_box = page.query_selector("#shop-about")
            assert desc_box, "Shop description box not found"
            assert desc_box.is_hidden()

            # Click description toggle - should open
            desc_toggle.click()
            page.wait_for_timeout(100)

            assert desc_toggle.get_attribute("aria-expanded") == "true"
            assert not desc_box.is_hidden()
            assert "warm inn" in desc_box.inner_text()

            # Click again - should close
            desc_toggle.click()
            page.wait_for_timeout(100)

            assert desc_toggle.get_attribute("aria-expanded") == "false"
            assert desc_box.is_hidden()

        finally:
            context.close()
            browser.close()


@pytest.mark.browser
@pytest.mark.django_db
def test_one_box_at_a_time(live_server):
    """Opening one box closes the other."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            _login_page(page, live_server)

            page.goto(_shop_detail_url(live_server))
            page.wait_for_load_state("networkidle")

            keeper_toggle = page.query_selector(".wm-shop-keeper-toggle")
            desc_toggle = page.query_selector(".wm-shop-about-toggle")
            keeper_box = page.query_selector("#keeper-about")
            desc_box = page.query_selector("#shop-about")

            # Open keeper bio
            keeper_toggle.click()
            page.wait_for_timeout(100)
            assert keeper_toggle.get_attribute("aria-expanded") == "true"
            assert not keeper_box.is_hidden()
            assert desc_toggle.get_attribute("aria-expanded") == "false"
            assert desc_box.is_hidden()

            # Open shop description - should close keeper bio
            desc_toggle.click()
            page.wait_for_timeout(100)
            assert desc_toggle.get_attribute("aria-expanded") == "true"
            assert not desc_box.is_hidden()
            assert keeper_toggle.get_attribute("aria-expanded") == "false"
            assert keeper_box.is_hidden()

            # Open keeper bio again - should close shop description
            keeper_toggle.click()
            page.wait_for_timeout(100)
            assert keeper_toggle.get_attribute("aria-expanded") == "true"
            assert not keeper_box.is_hidden()
            assert desc_toggle.get_attribute("aria-expanded") == "false"
            assert desc_box.is_hidden()

        finally:
            context.close()
            browser.close()


@pytest.mark.browser
@pytest.mark.django_db
def test_toggles_work_after_shop_switch(live_server):
    """Toggles still work after shop switcher swaps in another shop."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            _login_page(page, live_server)

            page.goto(_shop_detail_url(live_server))
            page.wait_for_load_state("networkidle")

            # Open keeper bio on first shop
            keeper_toggle = page.query_selector(".wm-shop-keeper-toggle")
            keeper_box = page.query_selector("#keeper-about")
            keeper_toggle.click()
            page.wait_for_timeout(100)
            assert keeper_toggle.get_attribute("aria-expanded") == "true"
            assert not keeper_box.is_hidden()
            assert "flour-dusted" in keeper_box.inner_text()

            # Use shop switcher to go to another shop
            switcher = page.query_selector(".wm-shop-switcher, [hx-get*='switcher']")
            if not switcher:
                # Try finding the select element
                switcher = page.query_selector("select.wm-shop-switcher, select[name='shop']")
            if switcher:
                # Click the switcher and select another option
                switcher.click()
                page.wait_for_timeout(100)
                option = page.query_selector("option[value]:not([value=''])")
                if option:
                    value = option.get_attribute("value")
                    selector = ".wm-shop-switcher, select[name='shop'], select.wm-shop-switcher"
                    page.select_option(selector, value)
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(500)  # wait for HTMX swap

                    # Re-find elements after swap
                    keeper_toggle = page.query_selector(".wm-shop-keeper-toggle")
                    keeper_box = page.query_selector("#keeper-about")
                    desc_toggle = page.query_selector(".wm-shop-about-toggle")
                    desc_box = page.query_selector("#shop-about")

                    # Toggles should still work
                    keeper_toggle.click()
                    page.wait_for_timeout(100)
                    assert keeper_toggle.get_attribute("aria-expanded") == "true"
                    assert not keeper_box.is_hidden()

                    desc_toggle.click()
                    page.wait_for_timeout(100)
                    assert desc_toggle.get_attribute("aria-expanded") == "true"
                    assert not desc_box.is_hidden()
                    assert keeper_toggle.get_attribute("aria-expanded") == "false"
                    assert keeper_box.is_hidden()

        finally:
            context.close()
            browser.close()


@pytest.mark.browser
@pytest.mark.django_db
def test_toggles_at_mobile_width(live_server):
    """Toggles work at mobile width (390px)."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 800})
        page = context.new_page()

        try:
            _login_page(page, live_server)

            page.goto(_shop_detail_url(live_server))
            page.wait_for_load_state("networkidle")

            keeper_toggle = page.query_selector(".wm-shop-keeper-toggle")
            desc_toggle = page.query_selector(".wm-shop-about-toggle")
            keeper_box = page.query_selector("#keeper-about")
            desc_box = page.query_selector("#shop-about")

            assert keeper_toggle, "Keeper toggle not found at mobile width"
            assert desc_toggle, "Description toggle not found at mobile width"

            keeper_toggle.click()
            page.wait_for_timeout(100)
            assert keeper_toggle.get_attribute("aria-expanded") == "true"
            assert not keeper_box.is_hidden()

            desc_toggle.click()
            page.wait_for_timeout(100)
            assert desc_toggle.get_attribute("aria-expanded") == "true"
            assert not desc_box.is_hidden()
            assert keeper_toggle.get_attribute("aria-expanded") == "false"
            assert keeper_box.is_hidden()

        finally:
            context.close()
            browser.close()
