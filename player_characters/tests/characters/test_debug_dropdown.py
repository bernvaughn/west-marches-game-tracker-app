import pytest
from django.test import Client
from django.urls import reverse
from items.models import Item
from ledger.services import Line, record

def _session_id(user):
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value

@pytest.mark.browser
def test_debug(transactional_db, live_server, club, player, funded, item):
    from playwright.sync_api import sync_playwright
    url = reverse("characters:detail", args=[club.slug, funded.pk])
    session_id = _session_id(player)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        errs = []
        page.on("console", lambda m: m.type == "error" and errs.append(m.text))
        page.goto(live_server.url + url)
        page.wait_for_load_state("networkidle")
        print("LOAD ERRORS:", errs)
        browser.close()
