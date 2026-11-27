"""Browser regression test for the item picker in the Give items inbox modal.

Covers two faults of the shared picker widget when it sits in an htmx modal:
- The search box had no ``name="q"``, so htmx sent no query and the list
  never narrowed.
- The ``<noscript><select name="items-0-item">`` fallback became a real field
  after the htmx swap. The POST then held two ``items-0-item`` values and
  Django read the last (empty) one, so the picked item was lost.

Login uses a server-side session cookie. Waits use Playwright ``expect``
assertions, which work under the app CSP (no unsafe-eval). Do not use
``page.wait_for_function``.

Run with: pytest -n0 -m browser accounts/tests/test_inbox_give_items_browser.py
"""

import pytest
from django.test import Client
from playwright.sync_api import expect, sync_playwright

from accounts.models import Membership, Message
from items.models import Item

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def give_items_page(club, club_admin, player, character, live_server):
    """Yield (page, posts): the inbox page of a logged-in admin and the POST bodies seen."""
    for name in ("Acid", "Longsword", "Rope"):
        Item.objects.create(club=club, name=name, value_cp=100)
    Message.objects.create(
        club=club,
        sender=Membership.objects.get(user=player, club=club),
        character=character,
        body="Please give me a sword",
    )

    client = Client()
    client.force_login(club_admin)
    session_id = client.cookies["sessionid"].value

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        posts = []
        page.on(
            "request", lambda r: posts.append(r.post_data or "") if r.method == "POST" else None
        )
        page.goto(f"{live_server.url}/c/{club.slug}/accounts/messages/")
        page.wait_for_load_state("networkidle")
        try:
            yield page, posts
        finally:
            context.close()
            browser.close()


def test_item_picker_search_and_grant(give_items_page):
    """Open Give items, search, pick, add, review, give: the item shows under Granted."""
    page, posts = give_items_page
    page.locator('a[aria-label="Give items"]').first.click()
    modal = page.locator("#app-modal")
    expect(modal.locator("input[name='items-0-item']").first).to_be_attached()

    # No noscript fallback select may leak into the live form.
    expect(modal.locator("select[name$='-item']")).to_have_count(0)

    # Searching narrows the list to the matching item.
    modal.locator("input[type='search'][name='q']").first.fill("Longsword")
    results = modal.locator(".wm-item-picker-result")
    expect(results).to_have_count(1)
    expect(results.first.locator(".fw-medium")).to_have_text("Longsword")

    # Pick it and fill the rest of the row.
    results.first.click()
    modal.locator("input[name='items-0-quantity']").fill("1")
    modal.locator("select[name='character']").select_option(label="Aria")
    modal.locator("input[name='note']").fill("Sword for Aria")
    modal.locator("input[name='date']").fill("2026-01-02")
    # Leave "mark handled" off: an items-only batch with it on hits a separate
    # ledger bug (Line(coins=0)) that is outside this test's scope.
    modal.locator("input[name='mark_handled']").uncheck()
    modal.get_by_role("button", name="Add another item/coin").click()

    # The add POST held exactly one non-empty items-0-item value.
    add_posts = [p for p in posts if "action=add" in p]
    assert len(add_posts) == 1
    values = [kv for kv in add_posts[0].split("&") if kv.startswith("items-0-item=")]
    assert len(values) == 1 and values[0] != "items-0-item=", values

    # The batch now holds the grant: review it, then give.
    expect(modal.get_by_text("Batch: 1 grant")).to_be_visible()
    modal.get_by_role("button", name="Review Batch").click()
    expect(modal.get_by_text("1 grant from this message.")).to_be_visible()
    modal.get_by_role("button", name="Give", exact=True).click()

    # The modal closes and the inbox row lists the item under Granted.
    expect(modal).to_be_hidden()
    granted = page.locator(".wm-granted").first
    expect(granted).to_contain_text("Longsword")
    expect(granted).to_contain_text("Aria")
