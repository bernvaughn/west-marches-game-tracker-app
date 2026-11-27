"""Tests for the quest turn-in celebration (Q6).

A successful turn-in stores a one-shot celebration in the session that the
quest board index renders as a panel reusing the loot fanfare markup.
Failed turn-ins never celebrate. The panel animates via container_fanfare.js
(replay button, sound off by default, reduced motion respected).
"""

import json
import time
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from accounts.models import Membership, User
from items.models import Item
from ledger.services import Line, record
from player_characters.models import Character, SelectedCharacter
from quests.models import Quest, QuestRequirement, QuestReward

DEMO_CLUB_SLUG = "demo"
FANFARE = "[data-fanfare]"
REVEAL_ITEM = "[data-wm-reveal-item]"
REPLAY_BUTTON = "[data-wm-fanfare-replay]"
SOUND_TOGGLE = "[data-wm-fanfare-sound]"

# Strict visibility check: every reveal item really occupies space, the fanfare
# is no longer armed, and the reveal row is not hidden. Replaces the old
# computed-style check, which passed even while the reveal parent was
# `display: none` (getComputedStyle reports opacity/transform on hidden nodes).
REVEAL_VISIBLE = (
    "(function () {"
    "  var fanfare = document.querySelector('[data-fanfare]');"
    "  var reveal = document.querySelector('[data-wm-reveal]');"
    "  var items = Array.from(document.querySelectorAll('[data-wm-reveal-item]'));"
    "  if (!fanfare || !reveal || !items.length) return false;"
    "  if (fanfare.classList.contains('wm-fanfare--armed')) return false;"
    "  if (getComputedStyle(reveal).display === 'none') return false;"
    "  return items.every(function (el) {"
    "    var r = el.getBoundingClientRect();"
    "    return r.width > 0 && r.height > 0;"
    "  });"
    "})()"
)


def _url(name, *args):
    return reverse(f"quests:{name}", args=["club-a", *args])


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _wait_for(page, expression, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"Timed out waiting for: {expression}")


def _turn_in(client, quest, character, *, htmx=False):
    headers = {"HTTP_HX-Request": "true"} if htmx else {}
    return client.post(_url("turn_in", quest.pk), {"character": character.pk}, **headers)


def _assert_panel(body, quest, character, rows):
    assert "data-fanfare" in body
    assert "data-wm-reveal" in body
    assert "data-wm-live" in body
    assert body.count("data-wm-reveal-item") == len(rows)
    assert quest.name in body
    assert character.name in body
    assert "Quest complete:" in body
    assert "js/container_fanfare.js" in body
    assert "css/container_fanfare.css" in body
    for row in rows:
        assert row["label"] in body


def _assert_no_console_csp(messages):
    csp = [m for m in messages if "content security policy" in m.lower()]
    assert not csp, csp


# ---------------------------------------------------------------------------
# Server-side markup tests
# ---------------------------------------------------------------------------


@pytest.mark.story("Q6")
def test_success_shows_celebration_panel(login, player, quest, character, item, give):
    """Item + coin rewards: panel with one reveal row per reward, fanfare assets linked."""
    give(character, item, 2)
    client = login(player)
    r = _turn_in(client, quest, character)
    assert r.status_code == 302
    assert r["Location"] == _url("index")

    body = client.get(_url("index")).content.decode()
    _assert_panel(
        body,
        quest,
        character,
        [{"symbol": "💰", "label": "1000 gp"}, {"symbol": "", "label": "1 Healing potion"}],
    )
    assert "💰" in body
    # The turn-in toast stays, now shown as a toast on the board.
    assert "wm-message-toast" in body
    assert f"{character.name} completed {quest.name}." in body


@pytest.mark.story("Q6")
def test_success_htmx_shows_celebration_panel(login, player, quest, character, item, give):
    """HTMX turn-in: 204 + HX-Redirect to the index, toast trigger kept, panel on the next load."""
    give(character, item, 2)
    client = login(player)
    r = _turn_in(client, quest, character, htmx=True)
    assert r.status_code == 204
    assert r["HX-Redirect"] == _url("index")
    trigger = json.loads(r["HX-Trigger"])
    assert set(trigger) == {"toast", "questCompleted"}
    assert trigger["toast"]["type"] == "success"
    assert trigger["toast"]["message"] == (
        f"✦ {character.name} completed {quest.name}! Reward: 1000 gp, 1 Healing potion"
    )
    assert trigger["questCompleted"] is True

    body = client.get(_url("index")).content.decode()
    _assert_panel(
        body,
        quest,
        character,
        [{"symbol": "💰", "label": "1000 gp"}, {"symbol": "", "label": "1 Healing potion"}],
    )
    assert "wm-message-toast" in body
    assert trigger["toast"]["message"] in body


@pytest.mark.story("Q6")
def test_coin_only_reward_still_celebrates(login, player, quest, character, item, give):
    """A coin-only reward still celebrates: one reveal row ("gp")."""
    quest.rewards.all().delete()
    QuestReward.objects.create(quest=quest, coins=500)
    give(character, item, 2)
    client = login(player)
    _turn_in(client, quest, character)

    body = client.get(_url("index")).content.decode()
    _assert_panel(body, quest, character, [{"symbol": "💰", "label": "500 gp"}])
    assert "500 gp" in body


@pytest.mark.story("Q6")
def test_no_rewards_no_panel_no_crash(login, player, quest, character, item, give):
    """A quest with no rewards: no panel, and the turn-in still succeeds."""
    quest.rewards.all().delete()
    give(character, item, 2)
    client = login(player)
    r = _turn_in(client, quest, character)
    assert r.status_code == 302
    assert client.session.get("quest_celebration") is None

    body = client.get(_url("index")).content.decode()
    assert "data-fanfare" not in body
    assert "Quest complete:" not in body


@pytest.mark.story("Q6")
def test_failed_turn_in_does_not_celebrate(
    login, player, quest, character, ended_quest, other_player, give
):
    """Missing items, a not-live quest, and no character: no panel on the index."""
    client = login(player)

    # Missing items: error, no completion, no celebration on the next index load.
    r = _turn_in(client, quest, character)
    assert r.status_code == 302
    assert client.session.get("quest_celebration") is None
    assert "data-fanfare" not in client.get(_url("index")).content.decode()

    # Not live: redirects straight to the index, still no celebration.
    r = client.post(_url("turn_in", ended_quest.pk), {"character": character.pk})
    assert r.status_code == 302
    assert r["Location"] == _url("index")
    assert "data-fanfare" not in client.get(_url("index")).content.decode()

    # No character for the member: error, no celebration.
    other_client = login(other_player)
    assert other_client.session.get("quest_celebration") is None
    _turn_in(other_client, quest, character)
    assert "data-fanfare" not in other_client.get(_url("index")).content.decode()


@pytest.mark.story("Q6")
def test_celebration_is_one_shot(login, player, quest, character, item, give):
    """The panel shows once: a reload of the index does not replay it."""
    give(character, item, 2)
    client = login(player)
    _turn_in(client, quest, character)
    assert "data-fanfare" in client.get(_url("index")).content.decode()
    assert "data-fanfare" not in client.get(_url("index")).content.decode()


@pytest.mark.story("Q6")
def test_club_mismatch_ignored(login, player, quest, character):
    """A celebration stored for another club is dropped on the index."""
    client = login(player)
    client.session["quest_celebration"] = {
        "club": "other-club",
        "quest": "Other quest",
        "character": "Someone",
        "rows": [{"symbol": "💰", "label": "500 gp"}],
    }
    client.session.save()

    body = client.get(_url("index")).content.decode()
    assert client.session.get("quest_celebration") is None
    assert "data-fanfare" not in body
    assert "Quest complete:" not in body


@pytest.mark.story("Q6")
def test_panel_markup_has_no_inline_style_or_script(login, player, quest, character, item, give):
    """CSP hygiene: the panel has no inline style attribute and no script block."""
    give(character, item, 2)
    client = login(player)
    _turn_in(client, quest, character)
    body = client.get(_url("index")).content.decode()

    start = body.index('<section class="wm-quest-celebration"')
    end = body.index("</section>", start) + len("</section>")
    panel = body[start:end]

    assert "<script" not in panel
    assert "style=" not in panel
    fanfare_start = panel.index("<div data-fanfare")
    fanfare_end = panel.index(">", fanfare_start)
    assert "aria-hidden" not in panel[fanfare_start:fanfare_end]


# ---------------------------------------------------------------------------
# Browser test: replay control and sound off by default
# ---------------------------------------------------------------------------


@pytest.mark.browser
@pytest.mark.story("Q6")
def test_turn_in_celebration_replay_and_sound_off(transactional_db, live_server):
    """Ready quest turn-in celebrates; replay works without POST, sound off by default."""
    _seed_demo()
    user = User.objects.get(email="bob@example.com")
    character = Character.objects.get(club__slug=DEMO_CLUB_SLUG, name="Tilda Brightwater")
    session_id = _session_id(user)

    club = character.club
    rope = Item.objects.create(club=club, name="Rope", value_cp=100)
    potion = Item.objects.create(club=club, name="Healing potion", symbol="🧪", value_cp=5000)
    today = timezone.localdate()
    quest = Quest.objects.create(
        club=club,
        name="Browser Celebration Quest",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=1),
    )
    QuestRequirement.objects.create(quest=quest, item=rope, quantity=1)
    QuestReward.objects.create(quest=quest, coins=200)
    QuestReward.objects.create(quest=quest, item=potion, quantity=1)
    record(character, "award", [Line(item=rope, quantity=1)], actor=user)

    # Make sure the turn-in page acts as this character.
    membership = Membership.objects.get(user=user, club=club)
    SelectedCharacter.objects.update_or_create(
        membership=membership, defaults={"character": character}
    )

    detail_url = reverse("quests:detail", args=[DEMO_CLUB_SLUG, quest.pk])
    index_url = reverse("quests:index", args=[DEMO_CLUB_SLUG])

    console_messages = []
    page_errors = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            page.on("console", lambda msg: console_messages.append(msg.text()))
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            page.goto(live_server.url + detail_url)
            page.wait_for_load_state("networkidle")

            turn_in = page.locator(f'button:has-text("Turn in as {character.name}")')
            turn_in.wait_for(state="visible", timeout=5000)

            post_requests = []
            page.on(
                "request", lambda req: post_requests.append(req) if req.method == "POST" else None
            )

            turn_in.click()

            # HTMX returns 204 + HX-Redirect: the browser lands on the quest board.
            page.wait_for_url(live_server.url + index_url)
            page.wait_for_load_state("networkidle")

            fanfare = page.locator(FANFARE)
            fanfare.wait_for(timeout=5000)

            panel = page.locator(FANFARE)
            assert quest.name in panel.locator("h2").text_content()
            assert character.name in panel.text_content()

            replay = page.locator(REPLAY_BUTTON)
            sound = page.locator(SOUND_TOGGLE)
            assert replay.count() == 1
            assert sound.count() == 1
            assert sound.get_attribute("aria-pressed") == "false"

            # Wait for the initial animation to finish: every reveal item
            # really visible (not just opacity/transform on a hidden node).
            _wait_for(page, REVEAL_VISIBLE)

            # Replay re-animates without posting to the server.
            post_requests.clear()
            replay.click()
            _wait_for(page, REVEAL_VISIBLE)
            assert len(post_requests) == 0

            _assert_no_console_csp(console_messages)
            assert not page_errors, page_errors
        finally:
            browser.close()
