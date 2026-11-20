"""Browser tests for the shop banner toggles (keeper bio and shop description).

The toggles live in static/js/shop_banner.js. These tests click them in a real
browser under the app CSP and check aria-expanded and the box hidden state.

Login uses a server-side session cookie, not the login form: the login view
rate-limits after two logins (accounts/ratelimit.py). Waits use Playwright
``expect`` assertions, which retry without eval, so they work under the CSP
(no unsafe-eval). Do not use ``page.wait_for_function`` here.
"""

import pytest
from django.core.management import call_command
from django.test import Client

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"
LANTERN_NAME = "The Rusty Lantern"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _shop_url(live_server, shop):
    return f"{live_server.url}/c/{DEMO_CLUB_SLUG}/shops/{shop.pk}/"


@pytest.fixture
def lantern(transactional_db):
    """Seed the demo club and return The Rusty Lantern (keeper Old Marta)."""
    from shops.models import Shop

    _seed_demo()
    return Shop.objects.get(club__slug=DEMO_CLUB_SLUG, name=LANTERN_NAME)


@pytest.fixture
def other_shops_have_banners(lantern):
    """Give every other demo shop a description and a keeper bio.

    The swapped-in banner then has both toggles, whichever shop the switcher
    offers. Runs before the browser starts: the ORM cannot run inside the
    Playwright event loop.
    """
    from shops.models import Shop

    Shop.objects.filter(club__slug=DEMO_CLUB_SLUG).exclude(pk=lantern.pk).update(
        description="Switched shop description.",
        keeper_description="Switched keeper bio.",
        keeper_name="Switched Keeper",
    )


@pytest.fixture
def shop_page(lantern, live_server):
    """Yield a function that opens a shop page in a logged-in browser page."""
    from playwright.sync_api import sync_playwright

    from accounts.models import User

    session_id = _session_id(User.objects.get(email=DEMO_PLAYER_EMAIL))

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        contexts = []

        def open_page(shop, width=1280):
            context = browser.new_context(viewport={"width": width, "height": 800})
            contexts.append(context)
            context.add_cookies(
                [{"name": "sessionid", "value": session_id, "url": live_server.url}]
            )
            page = context.new_page()
            errors = []
            # Only errors from the banner script count here. The stock poll's
            # hx-trigger filter has its own CSP EvalError (a separate task).
            page.on(
                "pageerror",
                lambda exc: errors.append(str(exc)) if "shop_banner" in (exc.stack or "") else None,
            )
            page.goto(_shop_url(live_server, shop))
            page.wait_for_load_state("networkidle")
            page.js_errors = errors
            return page

        try:
            yield open_page
        finally:
            for context in contexts:
                context.close()
            browser.close()


def _keeper(page):
    return page.locator(".wm-shop-keeper-toggle"), page.locator("#keeper-about")


def _about(page):
    return page.locator(".wm-shop-about-toggle"), page.locator("#shop-about")


def _assert_open(toggle, box):
    from playwright.sync_api import expect

    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(box).to_be_visible()


def _assert_closed(toggle, box):
    from playwright.sync_api import expect

    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(box).to_be_hidden()


def _check_both_toggles(page):
    """Open and close each toggle; opening one closes the other."""
    keeper_toggle, keeper_box = _keeper(page)
    about_toggle, about_box = _about(page)

    _assert_closed(keeper_toggle, keeper_box)
    _assert_closed(about_toggle, about_box)

    keeper_toggle.click()
    _assert_open(keeper_toggle, keeper_box)
    _assert_closed(about_toggle, about_box)

    about_toggle.click()
    _assert_open(about_toggle, about_box)
    _assert_closed(keeper_toggle, keeper_box)

    keeper_toggle.click()
    _assert_open(keeper_toggle, keeper_box)
    _assert_closed(about_toggle, about_box)

    keeper_toggle.click()
    _assert_closed(keeper_toggle, keeper_box)

    about_toggle.click()
    _assert_open(about_toggle, about_box)
    about_toggle.click()
    _assert_closed(about_toggle, about_box)


@pytest.mark.browser
def test_keeper_toggle_opens_and_closes_bio(lantern, shop_page):
    """A click on the keeper name opens the bio; a second click closes it."""
    from playwright.sync_api import expect

    page = shop_page(lantern)
    toggle, box = _keeper(page)

    _assert_closed(toggle, box)
    toggle.click()
    _assert_open(toggle, box)
    expect(box).to_contain_text("flour-dusted")
    toggle.click()
    _assert_closed(toggle, box)
    assert page.js_errors == []


@pytest.mark.browser
def test_description_toggle_opens_and_closes(lantern, shop_page):
    """A click on the description icon opens it; a second click closes it."""
    from playwright.sync_api import expect

    page = shop_page(lantern)
    toggle, box = _about(page)

    _assert_closed(toggle, box)
    toggle.click()
    _assert_open(toggle, box)
    expect(box).to_contain_text("warm inn")
    toggle.click()
    _assert_closed(toggle, box)
    assert page.js_errors == []


@pytest.mark.browser
def test_one_box_at_a_time(lantern, shop_page):
    """Opening one box closes the other."""
    page = shop_page(lantern)
    _check_both_toggles(page)
    assert page.js_errors == []


@pytest.mark.browser
def test_toggles_work_after_shop_switch(lantern, other_shops_have_banners, shop_page):
    """The toggles still work after the shop switcher swaps in another shop."""
    from playwright.sync_api import expect

    page = shop_page(lantern)

    # Leave a box open on the first shop. The swap must reset it.
    keeper_toggle, keeper_box = _keeper(page)
    keeper_toggle.click()
    _assert_open(keeper_toggle, keeper_box)

    page.locator(".shop-switcher .dropdown-toggle").click()
    target = page.locator(".shop-switcher .dropdown-item:not(.active)").first
    expect(target).to_be_visible()
    target_url = target.get_attribute("href")
    target_name = target.inner_text().strip()
    assert target_name != LANTERN_NAME
    target.click()

    expect(page).to_have_url(f"{page.url.split('/c/')[0]}{target_url}")
    expect(page.locator("#keeper-about")).to_contain_text("Switched keeper bio.")
    expect(page.locator("#shop-about")).to_contain_text("Switched shop description.")

    _check_both_toggles(page)
    assert page.js_errors == []


@pytest.mark.browser
def test_toggles_at_mobile_width(lantern, shop_page):
    """The toggles work at mobile width (390px)."""
    page = shop_page(lantern, width=390)
    _check_both_toggles(page)
    assert page.js_errors == []
