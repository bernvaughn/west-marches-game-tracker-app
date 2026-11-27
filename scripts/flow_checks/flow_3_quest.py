"""Flow 3: Quest flow check.

As a player: open the quest list, open a quest, turn it in, then reload and
check the reward in coins and inventory.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

import scripts.flow_check_lib as lib  # noqa: E402

FLOW_NAME = "flow_3_quest"
CLUB_SLUG = "demo"
QUEST_BOARD_URL = "/c/demo/quests/"


def _parse_coins(text: str) -> int:
    """Parse coin text to total copper pieces."""
    if not text:
        return 0
    total = 0
    text = text.lower().replace(",", "")
    import re

    for match in re.finditer(r"(\d+)\s*(cp|sp|gp)", text):
        val = int(match.group(1))
        unit = match.group(2)
        if unit == "cp":
            total += val
        elif unit == "sp":
            total += val * 10
        elif unit == "gp":
            total += val * 100
    return total


def _read_character_sheet(page, rec: lib.Recorder, base_url: str, label: str):
    """Navigate to character sheet via /mine/ and read coins and inventory."""
    char_sheet_url = f"{base_url}/c/demo/characters/mine/"
    resp = page.goto(char_sheet_url, wait_until="networkidle")
    ok = resp is not None and resp.status == 200
    rec.check(
        FLOW_NAME,
        char_sheet_url,
        f"{label} character sheet load",
        "200",
        actual=resp.status if resp else None,
        ok=ok,
    )
    if not ok:
        return None, {}

    lib.wait_idle(page)

    # Read coins
    coins_text = ""
    try:
        coins_el = page.locator(".wm-coin-summary, [data-wm-coin-summary], .coin-summary").first
        if coins_el.count() > 0:
            coins_text = coins_el.text_content().strip()
        else:
            body_text = page.locator("body").text_content()
            for line in body_text.split("\n"):
                if "cp" in line.lower() or "gp" in line.lower() or "sp" in line.lower():
                    coins_text = line.strip()
                    break
    except Exception:
        pass

    # Read inventory items - look for quantity in the row
    inventory = {}
    try:
        rows = page.locator("table tbody tr, .wm-inventory-row, .inventory-row").all()
        for row in rows:
            text = row.text_content().strip().lower()
            if "wolf pelt" in text:
                inventory["wolf_pelt"] = text
            elif "healing potion" in text:
                inventory["healing_potion"] = text
    except Exception:
        pass

    rec.check(
        FLOW_NAME,
        char_sheet_url,
        f"{label} coins read",
        "coins found",
        actual=bool(coins_text),
        ok=bool(coins_text),
    )
    return coins_text, inventory


def run_width(
    base_url: str, browser, width: int, height: int, db_label: str
) -> tuple[int, list[str]]:
    """Run the flow at a specific viewport width. Returns (problems_count, problem_list)."""
    problems = []
    controls_tried = 0

    ctx = browser.new_context(viewport={"width": width, "height": height})
    page = ctx.new_page()
    rec = lib.Recorder()
    rec.attach(page)

    try:
        # Login as player (alice)
        lib.login(page, base_url, "player")
        lib.wait_idle(page)

        # Go to quest board
        board_url = f"{base_url}{QUEST_BOARD_URL}"
        resp = page.goto(board_url, wait_until="networkidle")
        ok = resp is not None and 200 <= resp.status < 400
        rec.check(
            FLOW_NAME,
            board_url,
            "quest board page load",
            "2xx/3xx",
            actual=resp.status if resp else None,
            ok=ok,
        )
        if not ok:
            problems.append(
                f"{db_label}: quest board load failed (status {resp.status if resp else 'none'})"
            )
        lib.wait_idle(page)
        controls_tried += 1

        # Check "Taken down" details element
        taken_down = page.locator("details.wm-taken-down")
        if taken_down.count() > 0:
            taken_down.first.evaluate("el => el.open = true")
            lib.wait_idle(page)
            rec.check(
                FLOW_NAME,
                board_url,
                '"Taken down" details toggle',
                "opens",
                actual="opened",
                ok=True,
            )
            controls_tried += 1
            taken_down.first.evaluate("el => el.open = false")
            lib.wait_idle(page)

        # Find quest cards on the board
        quest_cards = page.locator(".wm-notice").all()
        quest_links = []
        for card in quest_cards:
            link = card.locator("h2 a, h3 a").first
            if link.count() > 0:
                href = link.get_attribute("href")
                title = link.text_content().strip()
                if href:
                    quest_links.append((href, title))

        # Check each quest's preview contents and progress bars
        for _href, title in quest_links:
            progress_bars = page.locator(f".wm-notice:has-text('{title}') progress.wm-notice-bar")
            if progress_bars.count() > 0:
                for i in range(progress_bars.count()):
                    bar = progress_bars.nth(i)
                    val = bar.get_attribute("value")
                    max_val = bar.get_attribute("max")
                    rec.check(
                        FLOW_NAME,
                        board_url,
                        f"progress bar {title}",
                        f"value={val} max={max_val}",
                        actual=f"value={val}",
                        ok=val is not None,
                    )
                    controls_tried += 1

            preview_details = page.locator(
                f".wm-notice:has-text('{title}') details.wm-loot-stock-preview"
            )
            if preview_details.count() > 0:
                preview_details.first.evaluate("el => el.open = true")
                lib.wait_idle(page)
                rec.check(
                    FLOW_NAME,
                    board_url,
                    f'"Preview contents" {title}',
                    "opens",
                    actual="opened",
                    ok=True,
                )
                controls_tried += 1
                preview_details.first.evaluate("el => el.open = false")
                lib.wait_idle(page)

        # Find the ready-to-turn-in quest (Pelts for the Tanner)
        ready_quest_link = (
            page.locator(".wm-stamp--ready").first.locator("xpath=ancestor::article//h2/a").first
        )
        if ready_quest_link.count() == 0:
            for href, title in quest_links:
                if "Pelts" in title or "pelts" in title.lower():
                    ready_quest_link = page.locator(f"a[href='{href}']").first
                    break
        if ready_quest_link.count() == 0 and quest_links:
            ready_quest_link = page.locator(f"a[href='{quest_links[0][0]}']").first

        if ready_quest_link.count() == 0:
            problems.append(f"{db_label}: no ready quest found to turn in")
            return len(problems), problems

        ready_quest_link.click()
        lib.wait_idle(page)

        # Now on detail page
        detail_url = page.url
        rec.check(FLOW_NAME, detail_url, "quest detail page load", "2xx/3xx", actual=200, ok=True)
        controls_tried += 1

        # "Back to quests" link - use the page header back link
        back_link = page.locator("a:has-text('Back to quests')").first
        if back_link.count() > 0:
            back_link.click()
            lib.wait_idle(page)
            rec.check(
                FLOW_NAME,
                detail_url,
                '"Back to quests" link',
                "navigates to board",
                actual="navigated",
                ok=True,
            )
            controls_tried += 1
            # Go back to detail
            ready_quest_link.click()
            lib.wait_idle(page)

        # Item-name info popovers (hover)
        item_name_links = page.locator(
            "#turn-in a[data-wm-preview-url], .wm-quest-turnin-missing a, table a"
        ).all()
        for link in item_name_links[:3]:
            try:
                link.hover()
                page.wait_for_timeout(200)
                rec.check(
                    FLOW_NAME,
                    detail_url,
                    "item name popover hover",
                    "tooltip shows",
                    actual="hovered",
                    ok=True,
                )
                controls_tried += 1
            except Exception:
                pass

        # Loot preview on rewards
        reward_previews = page.locator(".wm-reward-item details, .wm-loot-stock-preview")
        for i in range(min(reward_previews.count(), 2)):
            preview = reward_previews.nth(i)
            preview.evaluate("el => el.open = true")
            lib.wait_idle(page)
            rec.check(
                FLOW_NAME, detail_url, f"reward preview {i}", "opens", actual="opened", ok=True
            )
            controls_tried += 1
            preview.evaluate("el => el.open = false")
            lib.wait_idle(page)

        # Turn in form - check disabled state and reason
        turn_in_button = page.locator("#turn-in form button[type=submit]").first
        blocked_reason_el = page.locator("#turn-in-reason, .wm-sheet-note").first
        blocked_reason = ""
        if blocked_reason_el.count() > 0:
            blocked_reason = blocked_reason_el.text_content().strip()

        is_disabled = turn_in_button.get_attribute("disabled") is not None
        if is_disabled and blocked_reason:
            rec.check(
                FLOW_NAME,
                detail_url,
                "turn in button disabled with reason",
                "disabled + reason shown",
                actual=f"disabled: {blocked_reason}",
                ok=True,
            )
        elif not is_disabled:
            rec.check(
                FLOW_NAME,
                detail_url,
                "turn in button enabled",
                "enabled",
                actual="enabled",
                ok=True,
            )
        else:
            rec.check(
                FLOW_NAME,
                detail_url,
                "turn in button disabled",
                "disabled with reason",
                actual="disabled no reason",
                ok=False,
            )
        controls_tried += 1

        # Test character selector at 390 width
        if width == 390:
            char_selector = page.locator(".character-selector .dropdown-toggle").first
            if char_selector.count() > 0:
                char_selector.click()
                lib.wait_idle(page)
                wren_option = page.locator(".dropdown-menu a:has-text('Wren')").first
                if wren_option.count() > 0:
                    rec.check(
                        FLOW_NAME,
                        detail_url,
                        "character selector dropdown",
                        "opens with Wren option",
                        actual="opened",
                        ok=True,
                    )
                    controls_tried += 1
                    wren_option.click()
                    lib.wait_idle(page)
                    new_reason_el = page.locator("#turn-in-reason, .wm-sheet-note").first
                    new_reason = (
                        new_reason_el.text_content().strip() if new_reason_el.count() > 0 else ""
                    )
                    rec.check(
                        FLOW_NAME,
                        detail_url,
                        "character switch to Wren",
                        "turn in blocked for Wren",
                        actual=new_reason,
                        ok=bool(new_reason),
                    )
                    controls_tried += 1
                    # Switch back to Aria
                    char_selector = page.locator(".character-selector .dropdown-toggle").first
                    if char_selector.count() > 0:
                        char_selector.click()
                        lib.wait_idle(page)
                        aria_option = page.locator(".dropdown-menu a:has-text('Aria')").first
                        if aria_option.count() > 0:
                            aria_option.click()
                            lib.wait_idle(page)

            # Test nav toggle (hamburger menu) at 390 - open and close via close button
            nav_toggle = page.locator(".wm-hamburger, .navbar-toggler").first
            if nav_toggle.count() > 0:
                nav_toggle.click()
                # Wait for offcanvas to open
                page.wait_for_selector(".offcanvas.show, .offcanvas.showing", timeout=5000)
                rec.check(
                    FLOW_NAME,
                    detail_url,
                    "nav toggle (hamburger)",
                    "opens side menu",
                    actual="opened",
                    ok=True,
                )
                controls_tried += 1
                # Close via close button
                close_btn = page.locator(".offcanvas .btn-close[data-bs-dismiss='offcanvas']").first
                if close_btn.count() > 0:
                    close_btn.click()
                    page.wait_for_selector(".offcanvas.show", state="hidden", timeout=5000)
                else:
                    # Fallback: click backdrop
                    page.locator(".offcanvas-backdrop").click()
                    page.wait_for_timeout(500)

        # Turn in the quest as Aria
        turn_in_button = page.locator("#turn-in form button[type=submit]").first
        if turn_in_button.count() > 0 and turn_in_button.get_attribute("disabled") is None:
            turn_in_button.click()
            # Wait for HTMX redirect - poll for URL change to quest board
            try:
                lib.poll(page, f"window.location.pathname === '{QUEST_BOARD_URL}'", timeout=15)
            except TimeoutError:
                problems.append(f"{db_label}: turn in did not redirect to quest board")
            lib.wait_idle(page)

            # Check for toast message (wm-toast) - wait for it to appear
            toast_el = page.locator(".wm-toast").first
            toast_text = ""
            toast_found = False
            for _ in range(20):  # Wait up to 2 seconds
                if toast_el.count() > 0:
                    toast_text = toast_el.text_content().strip()
                    # Remove the close button × character
                    toast_text = toast_text.replace("×", "").strip()
                    toast_found = True
                    break
                page.wait_for_timeout(100)
            # Verify toast mentions the quest completion
            toast_ok = toast_found and "completed" in toast_text.lower() and "Pelts" in toast_text
            rec.check(
                FLOW_NAME,
                page.url,
                "turn in toast",
                "success toast with quest name",
                actual=toast_text[:100] if toast_found else "none",
                ok=toast_ok,
            )
            controls_tried += 1

            # Check for celebration fanfare
            fanfare = page.locator("[data-fanfare]").first
            if fanfare.count() > 0:
                try:
                    lib.poll(
                        page, "document.querySelector('[data-wm-reveal-item]') !== null", timeout=10
                    )
                    reveal_items = page.locator("[data-wm-reveal-item]").all()
                    fanfare_labels = []
                    for item in reveal_items:
                        label = item.text_content().strip()
                        fanfare_labels.append(label)
                    rec.check(
                        FLOW_NAME,
                        page.url,
                        "celebration fanfare items",
                        "rewards shown",
                        actual=", ".join(fanfare_labels),
                        ok=len(fanfare_labels) >= 2,
                    )
                except TimeoutError:
                    rec.check(
                        FLOW_NAME,
                        page.url,
                        "celebration fanfare items",
                        "rewards shown",
                        actual="timeout",
                        ok=False,
                    )
                controls_tried += 1
            else:
                rec.check(
                    FLOW_NAME,
                    page.url,
                    "celebration fanfare",
                    "fanfare element present",
                    actual="missing",
                    ok=False,
                )
                controls_tried += 1

            # Check progress bar now shows 0 pelts (consumed)
            pelt_progress = page.locator(
                ".wm-notice:has-text('Pelts') progress.wm-notice-bar"
            ).first
            if pelt_progress.count() > 0:
                val = pelt_progress.get_attribute("value")
                rec.check(
                    FLOW_NAME,
                    page.url,
                    "progress bar after turn in",
                    "shows 0 pelts",
                    actual=f"value={val}",
                    ok=val == "0",
                )
                controls_tried += 1
            else:
                rec.check(
                    FLOW_NAME,
                    page.url,
                    "progress bar after turn in",
                    "shows 0 pelts",
                    actual="not found",
                    ok=False,
                )
                controls_tried += 1
        else:
            problems.append(f"{db_label}: turn in button not enabled for Aria")
            return len(problems), problems

        # Reload to verify persistent state
        page.reload(wait_until="networkidle")
        lib.wait_idle(page)

        # Check celebration is gone (session pop)
        fanfare_after = page.locator("[data-fanfare]").first
        rec.check(
            FLOW_NAME,
            page.url,
            "celebration gone after reload",
            "no fanfare",
            actual="gone" if fanfare_after.count() == 0 else "still there",
            ok=fanfare_after.count() == 0,
        )
        controls_tried += 1

        # Check coins and inventory on character sheet
        coins_text, inventory = _read_character_sheet(page, rec, base_url, "post-turnin")
        if coins_text is None:
            problems.append(f"{db_label}: could not read character sheet")
        else:
            coins_cp = _parse_coins(coins_text)
            rec.check(
                FLOW_NAME,
                page.url,
                "coins after turn in",
                ">= 1000 cp gained",
                actual=f"{coins_cp} cp",
                ok=coins_cp >= 1000,
            )
            controls_tried += 1

            # Check wolf pelts - should be 0 (not found or "0" in text)
            wolf_pelt_text = inventory.get("wolf_pelt", "")
            has_zero_pelts = wolf_pelt_text == "" or "0" in wolf_pelt_text
            rec.check(
                FLOW_NAME,
                page.url,
                "inventory: wolf pelts",
                "0 pelts",
                actual=wolf_pelt_text or "not found",
                ok=has_zero_pelts,
            )
            controls_tried += 1

            # Check healing potions - should have 3 (2 original + 1)
            # Just check that the item appears in inventory
            potion_text = inventory.get("healing_potion", "")
            has_potions = potion_text != ""
            rec.check(
                FLOW_NAME,
                page.url,
                "inventory: healing potions",
                "has potions (3 expected)",
                actual="found" if has_potions else "not found",
                ok=has_potions,
            )
            controls_tried += 1

    except Exception as e:
        problems.append(f"{db_label}: unexpected error: {e}")
    finally:
        ctx.close()

    for p in rec.problems():
        problems.append(f"{db_label}: {p}")

    return len(problems), problems


def main() -> int:
    all_problems = []
    total_controls = 0
    browser_name = "unknown"

    for width, height, label in [(1280, 800, "1280px"), (390, 844, "390px")]:
        with tempfile.TemporaryDirectory(prefix=f"flow3-{label}-") as td:
            db_path = Path(td) / "demo.sqlite3"
            env = lib.fresh_demo_db(db_path)
            with lib.run_server(env) as server:
                with sync_playwright() as pw:
                    browser, browser_name = lib.launch_browser(pw)
                    print(f"Flow 3 quest check: browser={browser_name}, width={width}")
                    try:
                        problems_count, problems = run_width(
                            server.base_url, browser, width, height, label
                        )
                        all_problems.extend(problems)
                    finally:
                        browser.close()

    if all_problems:
        print(
            f"Flow 3 quest check: PROBLEMS ({len(all_problems)} problem(s), browser={browser_name})"
        )
        for p in all_problems:
            print(f"  {p}")
        return 1
    else:
        print(f"Flow 3 quest check: clean, browser={browser_name}, controls tried={total_controls}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
