"""Browser regression test for the inbox bulk Apply button.

Covers:
- Clicking Apply with no row ticked returns 200 with a visible "Tick at least
  one message" warning instead of a silent HTTP 400.
- A ticked bulk action still succeeds (no 4xx, no console error).

Login uses a server-side session cookie. Waits use Playwright ``expect``
assertions, which work under the app CSP (no unsafe-eval).

Run with: uv run pytest -m browser accounts/tests/test_inbox_bulk_browser.py
"""

import re

import pytest
from django.test import Client
from playwright.sync_api import expect, sync_playwright

from accounts.models import Membership, Message, User

BULK_RE = re.compile(r"/bulk-status/")


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _launch_page(pw, live_server, width, club_slug, session_id):
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": width, "height": 800})
    context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
    page = context.new_page()
    page.goto(f"{live_server.url}/c/{club_slug}/accounts/messages/?status=all")
    page.wait_for_load_state("networkidle")
    return browser, page


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_inbox_bulk_apply_nothing_ticked_warns(
    transactional_db, live_server, width, club, game_master
):
    """Apply with no row ticked: 200 + visible warning, no 4xx or console error."""
    gm_membership = Membership.objects.get(user=game_master, club=club)
    gm_membership.is_club_admin = True
    gm_membership.save()
    Message.objects.create(club=club, sender=gm_membership, body="Needs attention")
    Message.objects.create(club=club, sender=gm_membership, body="Also needs attention")

    session_id = _session_id(User.objects.get(email="gm@example.com"))

    bulk_status_errors = []
    console_errors = []

    with sync_playwright() as pw:
        browser, page = _launch_page(pw, live_server, width, club.slug, session_id)
        page.on(
            "response",
            lambda r: (
                bulk_status_errors.append(r.status)
                if BULK_RE.search(r.url) and r.status >= 400
                else None
            ),
        )
        page.on(
            "console",
            lambda m: console_errors.append(m.text) if m.type == "error" else None,
        )
        try:
            # Click Apply with no row ticked ("Mark handled" is the default).
            page.locator("#inbox-bulk-form button[type=submit]").click()

            # The visible warning must appear.
            expect(
                page.locator('.wm-toast:visible, [role="alert"]:visible').filter(
                    has_text="Tick at least one message"
                )
            ).to_be_visible(timeout=5000)

            # No 4xx/5xx on the bulk-status endpoint.
            assert not bulk_status_errors, bulk_status_errors
            # No console errors after the click.
            assert not console_errors, console_errors
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_inbox_bulk_apply_ticked_still_works(
    transactional_db, live_server, width, club, game_master
):
    """A ticked bulk action still changes status and returns no error."""
    gm_membership = Membership.objects.get(user=game_master, club=club)
    gm_membership.is_club_admin = True
    gm_membership.save()
    Message.objects.create(club=club, sender=gm_membership, body="To be closed")

    session_id = _session_id(User.objects.get(email="gm@example.com"))

    bulk_status_errors = []
    console_errors = []

    with sync_playwright() as pw:
        browser, page = _launch_page(pw, live_server, width, club.slug, session_id)
        page.on(
            "response",
            lambda r: (
                bulk_status_errors.append(r.status)
                if BULK_RE.search(r.url) and r.status >= 400
                else None
            ),
        )
        page.on(
            "console",
            lambda m: console_errors.append(m.text) if m.type == "error" else None,
        )
        try:
            # Tick the first row, choose Close, Apply.
            page.locator('input[name="message_ids"]').first.check()
            page.select_option("#inbox-bulk-bar select[name=status]", "closed")
            page.locator("#inbox-bulk-form button[type=submit]").click()

            # The list refreshes on success, clearing every tick.
            expect(page.locator('input[name="message_ids"]:checked')).to_have_count(0)

            # The ticked row now shows Closed.
            expect(
                page.locator("table.wm-data-table tbody tr").first.locator("td.wm-col-optional")
            ).to_contain_text("Closed")

            assert not bulk_status_errors, bulk_status_errors
            assert not console_errors, console_errors
        finally:
            browser.close()
