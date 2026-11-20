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

import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User
from downtime import services
from downtime.models import DowntimeAction, DowntimeResult
from player_characters.models import Character

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"
BAKERY_NAME = "Work at a bakery"
MODAL = "#app-modal .modal-content"


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
