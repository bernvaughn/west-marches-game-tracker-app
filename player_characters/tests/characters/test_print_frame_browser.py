"""Browser test: Print Session Pack prints from a hidden iframe.

The dashboard modal form has data-print-frame. On submit, print_frame.js
POSTs the form, loads the pack HTML into a hidden srcdoc iframe, and calls
print() on that frame. The print view never shows on the page, and the page
stays scrollable.
"""

import time

import pytest
from django.test import Client
from django.urls import reverse

# A capture-phase load listener on document runs before the listener that
# print_frame.js puts on the iframe, so the stub is in place before print().
# The stub fires afterprint, as a real dialog does when it closes.
STUB_FRAME_PRINT = """
window.__printCalls = 0;
window.__blockPrint = false;
window.__frameHtml = [];
document.addEventListener('load', function (event) {
  var frame = event.target;
  if (!frame || frame.tagName !== 'IFRAME' || !frame.hasAttribute('data-print-frame-target')) {
    return;
  }
  window.__frameHtml.push(frame.contentDocument.documentElement.outerHTML);
  frame.contentWindow.print = function () {
    window.__printCalls += 1;
    if (window.__blockPrint) throw new Error('Print blocked');
    frame.contentWindow.dispatchEvent(new Event('afterprint'));
  };
}, true);
"""

MODAL_FORM = "#app-modal form[data-print-frame]"
MODAL_OPEN = "document.body.classList.contains('modal-open')"


def _session_id(user):
    # Log in before Playwright starts: its event loop blocks sync ORM calls.
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


def _init_script_noise(message):
    # Playwright injects the init script into every frame. The print frame is
    # sandboxed without allow-scripts, so Chromium logs one error per inject.
    # Without an init script the frame logs nothing: print_frame.js strips
    # the page's own <script> tags.
    return message.location.get("url") == "about:srcdoc" and message.text.startswith(
        "Blocked script execution in 'about:srcdoc'"
    )


def _open_dashboard(pw, live_server, session_id, club):
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": 1000, "height": 400})
    context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
    context.add_init_script(STUB_FRAME_PRINT)
    page = context.new_page()
    errors = []

    def on_console(message):
        if message.type == "error" and not _init_script_noise(message):
            errors.append(message.text)

    page.on("console", on_console)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_server.url + reverse("accounts:player_dashboard", args=[club.slug]))
    page.wait_for_load_state("networkidle")
    return browser, page, errors


def _open_modal(page):
    page.locator("[data-app-modal]", has_text="Print Session Pack").click()
    page.wait_for_selector(MODAL_FORM, state="visible")


def _submit(page, pack_path):
    def is_pack_post(response):
        return response.request.method == "POST" and response.url.endswith(pack_path)

    with page.expect_response(is_pack_post) as resp:
        page.click(f"{MODAL_FORM} button[type=submit]")
    assert resp.value.status == 200


def _pack_path(club, character):
    return reverse("characters:print_session_pack", args=[club.slug, character.pk])


@pytest.mark.browser
def test_modal_submit_prints_from_hidden_frame(transactional_db, live_server, club, player, funded):
    from playwright.sync_api import sync_playwright

    session_id = _session_id(player)
    with sync_playwright() as pw:
        browser, page, errors = _open_dashboard(pw, live_server, session_id, club)
        try:
            _open_modal(page)
            _submit(page, _pack_path(club, funded))
            _wait_for(page, "window.__printCalls >= 1")
            _wait_for(page, f"!{MODAL_OPEN} && !document.querySelector('#app-modal.show')")
            page.wait_for_timeout(300)

            assert page.evaluate("window.__printCalls") == 1
            # The frame got the pack, and the page did not.
            assert "wm-sheet" in page.evaluate("window.__frameHtml[0]")
            assert "<script" not in page.evaluate("window.__frameHtml[0]")
            assert page.locator(".wm-sheet").count() == 0
            # afterprint removed the frame.
            assert page.locator("iframe[data-print-frame-target]").count() == 0
            # The page still scrolls.
            assert page.evaluate("getComputedStyle(document.body).overflow") != "hidden"
            assert page.evaluate("document.documentElement.scrollHeight > window.innerHeight")
            page.evaluate("window.scrollTo(0, 200)")
            assert page.evaluate("window.scrollY") > 0
            assert errors == []
        finally:
            browser.close()
    funded.refresh_from_db()
    assert funded.last_printed_at is not None


@pytest.mark.browser
def test_modal_shows_note_when_frame_print_throws(
    transactional_db, live_server, club, player, funded
):
    from playwright.sync_api import sync_playwright

    session_id = _session_id(player)
    with sync_playwright() as pw:
        browser, page, _errors = _open_dashboard(pw, live_server, session_id, club)
        try:
            page.evaluate("window.__blockPrint = true")
            _open_modal(page)
            _submit(page, _pack_path(club, funded))

            note = page.locator(f"{MODAL_FORM} [data-print-note] .alert-warning")
            note.wait_for(state="visible", timeout=5000)
            text = note.inner_text()
            assert "blocked the print dialog" in text
            assert "Ctrl+P" in text and "Cmd+P" in text
            assert page.evaluate("window.__printCalls") == 1
            assert page.locator("#app-modal").is_visible()
            assert page.locator("iframe[data-print-frame-target]").count() == 0
        finally:
            browser.close()


@pytest.mark.browser
def test_modal_shows_fetch_note_when_post_fails(
    transactional_db, live_server, club, player, funded
):
    from playwright.sync_api import sync_playwright

    pack_path = _pack_path(club, funded)
    session_id = _session_id(player)
    with sync_playwright() as pw:
        browser, page, _errors = _open_dashboard(pw, live_server, session_id, club)
        try:
            page.route(live_server.url + pack_path, lambda route: route.abort())
            _open_modal(page)
            page.click(f"{MODAL_FORM} button[type=submit]")

            note = page.locator(f"{MODAL_FORM} [data-print-note] .alert-warning")
            note.wait_for(state="visible", timeout=5000)
            assert "Could not prepare the print" in note.inner_text()
            assert page.evaluate("window.__printCalls") == 0
            assert page.locator("#app-modal").is_visible()
        finally:
            browser.close()


@pytest.mark.browser
def test_modal_options_reach_frame(transactional_db, live_server, club, player, funded):
    from playwright.sync_api import sync_playwright

    from map.models import HexMap

    HexMap.objects.create(club=club, name="The Marches")
    pack_path = _pack_path(club, funded)
    session_id = _session_id(player)
    with sync_playwright() as pw:
        browser, page, errors = _open_dashboard(pw, live_server, session_id, club)
        try:
            # Map is off by default.
            _open_modal(page)
            _submit(page, pack_path)
            _wait_for(page, "window.__frameHtml.length === 1")
            _wait_for(page, f"!{MODAL_OPEN}")
            assert "wm-map-print" not in page.evaluate("window.__frameHtml[0]")

            # Turn the map on.
            _open_modal(page)
            page.check("#opt-map")
            _submit(page, pack_path)
            _wait_for(page, "window.__frameHtml.length === 2")
            assert "wm-map-print" in page.evaluate("window.__frameHtml[1]")
            assert page.evaluate("window.__printCalls") == 2
            assert errors == []
        finally:
            browser.close()
