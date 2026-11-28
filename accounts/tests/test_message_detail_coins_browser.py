"""Browser regression test for message detail showing coins correctly (flow 10).

Covers:
- A coin-only grant shows the character name and "1 gp" (not "× 0").
- A mixed coin+item grant shows both.
- An item-only grant shows "Rope × 3".

Run with: uv run pytest -m browser accounts/tests/test_message_detail_coins_browser.py
"""

import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import Message, User
from ledger.models import LedgerEntry
from ledger.services import Line, record

# record imported from ledger.services above
from player_characters.models import Character

DEMO_CLUB_SLUG = "demo"
DEMO_ALICE_EMAIL = "alice@example.com"
DEMO_GM_EMAIL = "gm@example.com"
DEMO_PASSWORD = "demo-password"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _setup_message_with_coin_grant(club):
    """Create a message from Alice and record a 1 gp coin grant via ledger.services.record."""
    alice_user = User.objects.get(email=DEMO_ALICE_EMAIL)
    alice_mem = alice_user.memberships.get(club=club)
    aria = Character.objects.filter(owner=alice_mem, club=club).first()

    # Create a message from Alice to admins
    msg = Message.objects.create(
        club=club,
        sender=alice_mem,
        character=aria,
        body="Please give me some coins!",
    )

    # Record a 1 gp = 100 cp coin grant via ledger service
    record(
        aria,
        LedgerEntry.Kind.AWARD,
        [Line(coins=100)],
        note="Here is your coin",
        source_message=msg,
    )

    return msg, aria


def _setup_message_with_mixed_grant(club):
    """Create a message from Alice and record a mixed grant (coins + item)."""
    from items.models import Item

    alice_user = User.objects.get(email=DEMO_ALICE_EMAIL)
    alice_mem = alice_user.memberships.get(club=club)
    aria = Character.objects.filter(owner=alice_mem, club=club).first()

    msg = Message.objects.create(
        club=club,
        sender=alice_mem,
        character=aria,
        body="Mixed grant test",
    )

    # Create an item
    item = Item.objects.create(
        club=club, name="Rope", is_stacked=True, unit_name="ft", value_cp=100
    )

    # Record mixed grant: 50 cp (5 sp) + 3 ft of Rope
    record(
        aria,
        LedgerEntry.Kind.AWARD,
        [Line(coins=50), Line(item=item, quantity=3)],
        note="Mixed reward",
        source_message=msg,
    )

    return msg, aria, item


def _setup_message_with_item_grant(club):
    """Create a message from Alice and record an item-only grant."""
    from items.models import Item

    alice_user = User.objects.get(email=DEMO_ALICE_EMAIL)
    alice_mem = alice_user.memberships.get(club=club)
    aria = Character.objects.filter(owner=alice_mem, club=club).first()

    msg = Message.objects.create(
        club=club,
        sender=alice_mem,
        character=aria,
        body="Item grant test",
    )

    item = Item.objects.create(
        club=club, name="Rope", is_stacked=True, unit_name="ft", value_cp=100
    )

    record(
        aria,
        LedgerEntry.Kind.AWARD,
        [Line(item=item, quantity=3)],
        note="Here is rope",
        source_message=msg,
    )

    return msg, aria, item


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_message_detail_shows_coin_only_grant(transactional_db, live_server, width):
    """Coin-only grant shows character name and '1 gp', not '× 0'."""
    _seed_demo()
    club = User.objects.get(email=DEMO_GM_EMAIL).memberships.first().club
    msg, _ = _setup_message_with_coin_grant(club)

    alice = User.objects.get(email=DEMO_ALICE_EMAIL)
    session_id = _session_id(alice)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/accounts/messages/{msg.pk}/")
            page.wait_for_load_state("networkidle")

            # Find the "Items & Coins Granted" section
            granted_section = page.locator("h6:has-text('Items & Coins Granted')")
            granted_section.wait_for(timeout=5000)

            # The dd under that section should contain "1 gp"
            dd = granted_section.locator("xpath=following-sibling::dl[1]/dd").first
            dd.wait_for(timeout=5000)
            text = dd.inner_text()

            # Should show "1 gp" (or "1 gp" with coin symbols from coins_text)
            assert "1 gp" in text or "1 gp" in text.replace("\n", " "), (
                f"Expected '1 gp' in: {text}"
            )

            # Must NOT show the buggy "× 0"
            assert "× 0" not in text, f"Should not contain '× 0' but got: {text}"

            # Character name is in dt, grant details in dd - check the dl for both
            dl = granted_section.locator("xpath=following-sibling::dl[1]").first
            dl_text = dl.inner_text()
            assert "Aria Windrunner" in dl_text
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_message_detail_shows_mixed_grant(transactional_db, live_server, width):
    """Mixed coin+item grant shows both coins and item."""
    _seed_demo()
    club = User.objects.get(email=DEMO_GM_EMAIL).memberships.first().club
    msg, _, item = _setup_message_with_mixed_grant(club)

    alice = User.objects.get(email=DEMO_ALICE_EMAIL)
    session_id = _session_id(alice)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/accounts/messages/{msg.pk}/")
            page.wait_for_load_state("networkidle")

            granted_section = page.locator("h6:has-text('Items & Coins Granted')")
            granted_section.wait_for(timeout=5000)

            dd = granted_section.locator("xpath=following-sibling::dl[1]/dd").first
            dd.wait_for(timeout=5000)
            text = dd.inner_text()

            # Should show "5 sp" (50 cp) — coins_text formats 50 cp as "5 sp"
            assert "5 sp" in text or "5 sp" in text.replace("\n", " "), (
                f"Expected '5 sp' in: {text}"
            )

            # Should show item "Rope × 3"
            assert "Rope" in text and "3" in text, f"Expected 'Rope' and '3' in: {text}"

            # Must NOT show the buggy "× 0"
            assert "× 0" not in text, f"Should not contain '× 0' but got: {text}"

            # Character name is in dt, grant details in dd - check the dl for both
            dl = granted_section.locator("xpath=following-sibling::dl[1]").first
            dl_text = dl.inner_text()
            assert "Aria Windrunner" in dl_text
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [1280, 390])
def test_message_detail_shows_item_only_grant(transactional_db, live_server, width):
    """Item-only grant shows item name and quantity."""
    _seed_demo()
    club = User.objects.get(email=DEMO_GM_EMAIL).memberships.first().club
    msg, _, item = _setup_message_with_item_grant(club)

    alice = User.objects.get(email=DEMO_ALICE_EMAIL)
    session_id = _session_id(alice)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.goto(f"{live_server.url}/c/{DEMO_CLUB_SLUG}/accounts/messages/{msg.pk}/")
            page.wait_for_load_state("networkidle")

            granted_section = page.locator("h6:has-text('Items & Coins Granted')")
            granted_section.wait_for(timeout=5000)

            dd = granted_section.locator("xpath=following-sibling::dl[1]/dd").first
            dd.wait_for(timeout=5000)
            text = dd.inner_text()

            # Should show item "Rope × 3"
            assert "Rope" in text and "3" in text, f"Expected 'Rope' and '3' in: {text}"

            # Must NOT show the buggy "× 0"
            assert "× 0" not in text, f"Should not contain '× 0' but got: {text}"

            # Character name is in dt, grant details in dd - check the dl for both
            dl = granted_section.locator("xpath=following-sibling::dl[1]").first
            dl_text = dl.inner_text()
            assert "Aria Windrunner" in dl_text
        finally:
            browser.close()
