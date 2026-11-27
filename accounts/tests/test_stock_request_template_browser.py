"""Browser regression test for the stock request form template dropdown removal.

The stock request form previously had a dead "Template" dropdown (inherited from
MessageForm) that did nothing. This test verifies the dropdown is removed and
only the Request textarea appears.
"""

import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"
DEMO_PASSWORD = "demo-password"
MODAL = "#app-modal .modal-content"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_stock_request_form_has_no_template_dropdown(transactional_db, live_server, width):
    """The stock request form has no Template dropdown; only Request textarea."""
    _seed_demo()
    user = User.objects.get(email=DEMO_PLAYER_EMAIL)
    session_id = _session_id(user)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/accounts/messages/stock/new/")
            page.wait_for_load_state("networkidle")

            # Assert the Template select does not exist
            template_select = page.locator("select[name='template'], #id_template")
            assert template_select.count() == 0, "Template dropdown should not exist"

            # Assert the Request textarea exists
            textarea = page.locator("textarea[name='body'], #id_body")
            assert textarea.count() == 1, "Request textarea should exist"
            assert textarea.is_visible(), "Request textarea should be visible"

            # Assert the form has the submit button (specifically the one in the wm-form)
            submit = page.locator('.wm-form button[type="submit"]')
            assert submit.count() == 1, "Submit button should exist"
        finally:
            browser.close()


@pytest.mark.django_db
def test_stock_request_form_html_no_template_field(club, player, character, login):
    """Server-side: stock request page HTML has no name='template'."""
    from django.urls import reverse

    c = login(player)
    url = reverse("accounts:stock_request_new", args=[club.slug])
    response = c.get(url)
    html = response.content.decode()
    # No template select
    assert 'name="template"' not in html
    assert 'id="id_template"' not in html
    # Body textarea exists
    assert 'name="body"' in html
    assert 'id="id_body"' in html


@pytest.mark.django_db
def test_message_new_form_still_has_quick_template_buttons(club, player, character, login):
    """The message_new page still has quick-template buttons (not the dropdown)."""
    from django.urls import reverse

    c = login(player)
    url = reverse("accounts:message_new", args=[club.slug])
    response = c.get(url)
    html = response.content.decode()
    # No template dropdown (it was never rendered here anyway)
    assert 'name="template"' not in html
    assert 'id="id_template"' not in html
    # But the quick-template buttons are present
    assert 'data-template="loot"' in html
    assert 'data-template="map"' in html
    assert 'data-template="shop"' in html
    assert 'data-template="other"' in html
    assert "Loot correction" in html
    assert "Map credit" in html
    assert "Shop stock request" in html
    assert "Other" in html
    # The template script is loaded
    assert "inbox_templates.js" in html
