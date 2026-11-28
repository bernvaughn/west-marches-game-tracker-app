"""Browser regression test for the message detail back link.

A player's "Back to inbox" link on the message detail page must not lead to
the admin inbox (which returns 403 for players). The link points to
accounts:message_new for senders (players) and to accounts:message_inbox
for admins.
"""

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from accounts.models import Message, User

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"
DEMO_ADMIN_EMAIL = "gm@example.com"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _alice_message_pk():
    """Look up Alice's seeded message; the pk is not stable across test runs."""
    message = Message.objects.filter(sender__user__email=DEMO_PLAYER_EMAIL).order_by("pk").first()
    assert message is not None, "seed_demo should create a message from Alice"
    return message.pk


def _open_detail_and_click_back(live_server, width, email):
    """Open Alice's message detail as `email`, click Back, return (href, landing page info)."""
    _seed_demo()
    session_id = _session_id(User.objects.get(email=email))
    detail_path = f"/c/{DEMO_CLUB_SLUG}/accounts/messages/{_alice_message_pk()}/"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            response = page.goto(f"{live_server.url}{detail_path}")
            assert response is not None and response.status == 200
            page.wait_for_load_state("networkidle")

            back_link = page.locator(".wm-back-link")
            assert back_link.count() == 1, "Back link should exist"
            href = back_link.get_attribute("href")

            with page.expect_navigation() as nav:
                back_link.click()
            landing = nav.value
            page.wait_for_load_state("networkidle")
            return href, landing.status, page.url
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_player_back_link_leads_to_message_new(transactional_db, live_server, width):
    """Player clicks Back on message detail and lands on message_new (200, not inbox 403)."""
    href, status, url = _open_detail_and_click_back(live_server, width, DEMO_PLAYER_EMAIL)

    assert href.rstrip("/").endswith("/messages/new"), f"Expected message_new href, got {href}"
    assert status == 200, f"Back link landed on HTTP {status} at {url}"
    assert url.rstrip("/").endswith("/accounts/messages/new"), f"Unexpected landing URL {url}"


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_admin_back_link_leads_to_inbox(transactional_db, live_server, width):
    """Admin clicks Back on the same message and lands on the inbox (200)."""
    href, status, url = _open_detail_and_click_back(live_server, width, DEMO_ADMIN_EMAIL)

    assert not href.rstrip("/").endswith("/messages/new"), f"Admin href should be inbox: {href}"
    assert status == 200, f"Back link landed on HTTP {status} at {url}"
    assert url.rstrip("/").endswith("/accounts/messages"), f"Unexpected landing URL {url}"


@pytest.mark.django_db
def test_message_detail_back_url_for_player(club, player, character, login):
    """Server-side: player's message_detail back_url targets message_new."""
    from accounts.models import Membership

    mem = Membership.objects.get(user=player, club=club)
    msg = Message.objects.create(club=club, sender=mem, character=character, body="Hello admins")
    c = login(player)
    url = reverse("accounts:message_detail", args=[club.slug, msg.pk])
    response = c.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    new_url = reverse("accounts:message_new", args=[club.slug])
    inbox_url = reverse("accounts:message_inbox", args=[club.slug])
    assert new_url in html, f"message_new URL {new_url} should be in the page"
    # The back link should target message_new, not the inbox
    assert f'href="{new_url}"' in html, f"Back link should target {new_url}"
    assert f'href="{inbox_url}"' not in html, (
        f"Back link should not target {inbox_url} for a player"
    )
    assert "Back to messages" in html


@pytest.mark.django_db
def test_message_detail_back_url_for_admin(club, club_admin, player, character, login):
    """Server-side: admin's message_detail back_url targets message_inbox."""
    from accounts.models import Membership

    mem = Membership.objects.get(user=player, club=club)
    msg = Message.objects.create(club=club, sender=mem, character=character, body="Hello admins")
    c = login(club_admin)
    url = reverse("accounts:message_detail", args=[club.slug, msg.pk])
    response = c.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    inbox_url = reverse("accounts:message_inbox", args=[club.slug])
    assert f'href="{inbox_url}"' in html, f"Back link should target {inbox_url} for an admin"
    assert "Back to inbox" in html
