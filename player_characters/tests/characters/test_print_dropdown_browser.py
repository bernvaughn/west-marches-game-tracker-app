"""Browser test: the per-item print dropdown opens above the table and is clickable.

The sticky actions cells (``td.wm-row-actions-cell, position: sticky, z-index: 1``)
paint over the open dropdown menu because each cell is its own stacking context.
Lifting the open cell above its siblings lets the player pick "Full page" /
"Grid spot".

CSP is script-src 'self', so page.wait_for_function cannot run; page.evaluate
is used instead.
"""

import pytest
from django.test import Client
from django.urls import reverse

from items.models import Item
from ledger.services import Line, record


def _session_id(user):
    # Log in before Playwright starts: its event loop blocks sync ORM calls.
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _open_sheet(pw, live_server, session_id, url, width, height):
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": width, "height": height})
    context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
    page = context.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_server.url + url)
    page.wait_for_load_state("networkidle")
    return browser, page, errors


def _centre(box):
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _element_from_point(page, x, y):
    return page.evaluate(
        "([x, y]) => {"
        "  const el = document.elementFromPoint(x, y);"
        "  return el && { tag: el.tagName, cls: el.className || '', text: el.textContent || '', href: el.href || '' };"
        "}",
        [x, y],
    )


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(1280, 800), (390, 800)])
def test_print_dropdown_items_are_clickable(
    transactional_db, live_server, club, player, funded, item, width, height
):
    from playwright.sync_api import sync_playwright

    # A second row sits below the open menu, reproducing the overlap.
    item_b = Item.objects.create(club=club, name="Torch", value_cp=1)
    record(funded, "award", [Line(item=item_b, quantity=1)])

    url = reverse("characters:detail", args=[club.slug, funded.pk])
    print_url = reverse("characters:print_item", args=[club.slug, funded.pk, item.pk])
    session_id = _session_id(player)

    with sync_playwright() as pw:
        browser, page, errors = _open_sheet(pw, live_server, session_id, url, width, height)
        try:
            # Open the first row's print dropdown (in its row-actions cell, not the header menu).
            page.locator(".wm-row-actions-cell [data-bs-toggle=\"dropdown\"]").first.click()
            menu = page.locator(".wm-row-actions-cell .dropdown-menu.show")
            menu.wait_for(state="visible")

            items = menu.locator(".dropdown-item")
            assert items.count() >= 2

            # Each menu item must be the topmost element at its own centre.
            for i in range(2):
                box = items.nth(i).bounding_box()
                assert box is not None, f"dropdown item {i} has no box"
                cx, cy = _centre(box)
                hit = _element_from_point(page, cx, cy)
                assert hit["tag"] == "A", f"item {i} not hit: {hit}"
                assert "dropdown-item" in hit["cls"], f"item {i} not hit: {hit}"
                assert hit["text"].strip() in ("Full page", "Grid spot"), f"item {i} not hit: {hit}"

            # Click "Full page": the item's print page loads with status 200.
            with page.expect_response(
                lambda r: r.request.method == "GET"
                and r.url.startswith(live_server.url + print_url)
            ) as resp:
                items.first.click()
            assert resp.value.status == 200
            assert page.url.startswith(live_server.url + print_url)
            assert errors == []
        finally:
            browser.close()
