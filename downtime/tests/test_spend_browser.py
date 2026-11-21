"""Regression test: double-clicking "Take the job" spends once.

The spend form (downtime/templates/downtime/play/_jobs.html) posts with HTMX
and the response loads into #app-modal, leaving the page in place. Without
hx-disabled-elt / hx-sync a double-click sends two POSTs and the character is
charged twice. The form now disables its button while the request runs
(hx-disabled-elt="find button") and drops repeat requests while one is in
flight (hx-sync="this:drop"), so a double-click charges exactly once.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.management import call_command
from django.db import connection
from django.test import Client

from accounts.models import User
from downtime import services
from downtime.models import DowntimeAction, DowntimeResult
from player_characters.models import Character

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"
BAKERY_NAME = "Work at a bakery"
MODAL = "#app-modal .modal-content"
SPIN_AGAIN = ".wm-spin-again"


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


def _db_state(character):
    """Snapshot the character's downtime state.

    Playwright's sync API runs an event loop, which Django's ORM refuses to use
    from the same thread, so the queries run in a worker thread.
    """

    def query():
        try:
            return {
                "balance": services.balance(character),
                "results": DowntimeResult.objects.filter(character=character).count(),
                "point_entries": character.downtime_point_entries.count(),
                "ledger": character.ledger_entries.count(),
            }
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(query).result()


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_spin_again_enabled_at_zero_points(transactional_db, live_server, width):
    """
    Spin again is enabled when balance is 0 after spending the last point.
    Clicking it replays the wheel without changing balance, ledger, or result count.
    """
    _seed_demo()

    from playwright.sync_api import sync_playwright

    user = User.objects.get(email="bob@example.com")
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name__startswith="Borin")
    action = DowntimeAction.objects.get(club__slug=DEMO_CLUB_SLUG, name=BAKERY_NAME)
    assert action.cost == 1, "Test expects a 1-point action"

    session_id = _session_id(user)
    initial_balance = services.balance(character)
    assert initial_balance == 1, "Borin should start with 1 point"
    initial_results = DowntimeResult.objects.filter(character=character).count()
    initial_point_entries = character.downtime_point_entries.count()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/downtime/")
            page.wait_for_load_state("networkidle")

            page.locator(
                f'li.wm-chalk-job:has(h3:has-text("{BAKERY_NAME}")) button[type=submit]'
            ).click()
            page.wait_for_selector(f"{MODAL} [data-downtime-wheel]", state="attached")

            # The spend is committed once the modal shows. Snapshot the state now.
            # The wheel outcome is random, so the coin ledger may or may not gain a
            # row: compare the replay against this snapshot, not against a fixed count.
            after_spend = _db_state(character)
            assert after_spend["balance"] == 0
            assert after_spend["results"] == initial_results + 1
            assert after_spend["point_entries"] == initial_point_entries + 1

            chosen_before = page.locator(f"{MODAL} [data-downtime-wheel]").get_attribute(
                "data-chosen"
            )
            # Tag the first wheel node so a replaced node can be told apart.
            page.evaluate(
                "document.querySelector('#app-modal [data-downtime-wheel]')"
                ".setAttribute('data-first-spin', '1')"
            )

            # "Spin again" must be enabled at 0 points, and the click must hit /replay/.
            spin_again = page.locator(SPIN_AGAIN)
            assert spin_again.is_enabled(), "Spin again should be enabled at 0 points"
            with page.expect_response(lambda r: "/replay/" in r.url) as replay:
                spin_again.click()
            assert replay.value.status == 200

            # The replay swaps in a fresh wheel node holding the same stored result.
            _wait_for(
                page,
                "!document.querySelector('#app-modal [data-downtime-wheel]')"
                ".hasAttribute('data-first-spin')",
            )
            wheel = page.locator(f"{MODAL} [data-downtime-wheel]")
            assert wheel.get_attribute("data-chosen") == chosen_before
        finally:
            browser.close()

    # Replay is free: nothing changed since the spend.
    assert _db_state(character) == after_spend


@pytest.mark.browser
def test_double_click_take_the_job_charges_once(transactional_db, live_server):
    """A double-click on "Take the job" charges the cost once, once only."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    user = User.objects.get(email=DEMO_PLAYER_EMAIL)
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name__startswith="Aria")
    action = DowntimeAction.objects.get(club__slug=DEMO_CLUB_SLUG, name=BAKERY_NAME)
    session_id = _session_id(user)
    initial_balance = services.balance(character)
    initial_results = DowntimeResult.objects.filter(character=character).count()

    held_routes = []
    released = threading.Event()

    def hold_spend(route):
        if route.request.method == "POST":
            held_routes.append(route)
            released.wait(timeout=10)
        route.continue_()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.route("**/spend/*", hold_spend)

            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/downtime/")
            page.wait_for_load_state("networkidle")

            # Double-click "Take the job" on the bakery job card.
            page.locator(
                f'li.wm-chalk-job:has(h3:has-text("{BAKERY_NAME}")) button[type=submit]'
            ).dblclick()

            # Let the held request proceed to the server.
            released.set()

            # The result loads into the modal once the spend completes.
            page.wait_for_selector(MODAL, state="visible", timeout=5000)
        finally:
            browser.close()

    character.refresh_from_db()
    assert services.balance(character) == initial_balance - action.cost
    assert DowntimeResult.objects.filter(character=character).count() == initial_results + 1


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_balance_updates_after_spend(transactional_db, live_server, width):
    """After spending downtime points, the balance and button state update on modal close.

    Steps:
    1. Open downtime page (balance shows 2 points)
    2. Click "Take the job" on Work at a bakery (cost 1)
    3. Close the result modal with the Close button
    4. Assert balance shows "1 downtime point"
    5. Click "Take the job" again
    6. Close the result modal
    7. Assert balance shows "0 downtime points"
    8. Assert the "Take the job" button is disabled with reason text
    """
    _seed_demo()

    from playwright.sync_api import sync_playwright

    user = User.objects.get(email=DEMO_PLAYER_EMAIL)
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name__startswith="Aria")
    action = DowntimeAction.objects.get(club__slug=DEMO_CLUB_SLUG, name=BAKERY_NAME)
    session_id = _session_id(user)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/downtime/")
            page.wait_for_load_state("networkidle")

            # Initial balance should be 2 points
            balance = page.locator("#downtime-balance")
            expect = __import__("playwright.sync_api", fromlist=["expect"]).expect
            expect(balance).to_contain_text("2 downtime point")

            # First spend: click Take the job
            job_button = page.locator(
                "li.wm-chalk-job", has=page.locator("h3", has_text=BAKERY_NAME)
            ).locator("button[type=submit]")
            job_button.click()

            # Wait for modal to appear
            page.wait_for_selector(MODAL, state="visible", timeout=5000)

            # Close the modal with Close button
            page.locator("#app-modal .modal-footer button[data-bs-dismiss='modal']").click()

            # Wait for modal to close
            page.wait_for_selector(MODAL, state="hidden", timeout=5000)

            # Assert balance updated to 1 point
            expect(balance).to_contain_text("1 downtime point")

            # Second spend: click Take the job again
            job_button.click()

            # Wait for modal to appear
            page.wait_for_selector(MODAL, state="visible", timeout=5000)

            # Close the modal
            page.locator("#app-modal .modal-footer button[data-bs-dismiss='modal']").click()

            # Wait for modal to close
            page.wait_for_selector(MODAL, state="hidden", timeout=5000)

            # Assert balance updated to 0 points
            expect(balance).to_contain_text("0 downtime point")

            # Assert button is disabled with reason text
            expect(job_button).to_be_disabled()
            reason = page.locator(f"#why-{action.pk}")
            expect(reason).to_contain_text("Not enough downtime points")

        finally:
            browser.close()

    # Verify server state matches
    character.refresh_from_db()
    assert services.balance(character) == 0
