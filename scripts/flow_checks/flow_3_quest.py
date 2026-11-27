"""Flow 3: quest flow check.

As a player (alice): open the quest list, open a quest, turn it in, then reload
and check the reward in coins and inventory.

Runs at 1280 and 390 wide. Each width gets its own fresh seeded demo database
and server, because a turn-in changes state. Firefox is used if it launches,
else Chromium; the browser name is printed.

Every control is used with a real click and logged through ``Recorder.check``
with the visible result and the HTTP status read from the response. Rewards are
checked against a baseline read from the character sheet before the turn-in:

* Pelts for the Tanner: 3 Wolf pelts are handed in, +1000 cp and 1 Healing
  potion are paid.
* Maps for the Cartographer: 10 Parchment are handed in (25 -> 15), +500 cp.

Coins are stored in copper (1 gp = 100 cp); the board and the sheet show
1000 cp as "10 gp".

Run: ``python scripts/flow_checks/flow_3_quest.py`` (exit 0 clean, 1 on problems).
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

import scripts.flow_check_lib as lib  # noqa: E402

FLOW = "flow_3_quest"
BOARD_PATH = "/c/demo/quests/"
SHEET_PATH_RE = re.compile(r"/c/demo/characters/\d+/$")

PELTS = "Pelts for the Tanner"
MAPS = "Maps for the Cartographer"
PACK = "Pack for the Quartermaster"
OLD = "Old Notice"

CP_PER = {"cp": 1, "sp": 10, "gp": 100, "pp": 1000}

# Extra rows added to the fresh demo database so every board control exists:
# a quest paying a container (the "Preview contents" toggle) and an ended
# quest (the "Taken down" toggle). Neither touches Aria's items or coins.
SEED_EXTRAS = """
from datetime import timedelta
from django.utils import timezone
from accounts.models import Club
from items.models import Item
from quests.models import Quest, QuestRequirement, QuestReward

club = Club.objects.get(slug="demo")
today = timezone.localdate()
pelt = Item.objects.get(club=club, name="Wolf pelt")
pack = (
    Item.objects.filter(club=club, is_container=True, slots__isnull=False)
    .distinct()
    .order_by("name")
    .first()
)
chest = Quest.objects.create(
    club=club,
    name="__PACK_QUEST__",
    description="The quartermaster pays in packs.",
    start_date=today - timedelta(days=1),
)
QuestRequirement.objects.create(quest=chest, item=pelt, quantity=99)
QuestReward.objects.create(quest=chest, item=pack, quantity=1, coins=0)
old = Quest.objects.create(
    club=club,
    name="__OLD_QUEST__",
    description="This notice is past its end date.",
    start_date=today - timedelta(days=30),
    end_date=today - timedelta(days=1),
)
QuestRequirement.objects.create(quest=old, item=pelt, quantity=1)
QuestReward.objects.create(quest=old, item=None, coins=100, quantity=0)
print(pack.name)
""".replace("__PACK_QUEST__", PACK).replace("__OLD_QUEST__", OLD)

SHEET_JS = """() => {
  const rows = [...document.querySelectorAll('tr')]
    .filter(tr => tr.querySelector('.wm-sheet-item-name'))
    .map(tr => {
      const name = tr.querySelector('.wm-sheet-item-name').cloneNode(true);
      name.querySelectorAll('.wm-item-symbol, .wm-item-info').forEach(e => e.remove());
      const inline = tr.querySelector('.wm-sheet-owned-inline');
      const cells = [...tr.querySelectorAll('td.wm-col-optional')].map(td => td.textContent.trim());
      return {name: name.textContent.trim(), inline: inline ? inline.textContent.trim() : null,
              owned: cells.length ? cells[0] : null};
    });
  const coins = [...document.querySelectorAll('.wm-sheet-coins-total .coin')]
    .map(e => e.textContent.trim());
  return {rows, coins};
}"""


def parse_coins(parts: list[str]) -> int | None:
    """Total copper from coin texts like ["60 gp", "5 sp"]; None if any part is unreadable."""
    total = 0
    for part in parts:
        match = re.fullmatch(r"([\d,]+)\s*(pp|gp|sp|cp)", part.strip().lower())
        if not match:
            return None
        total += int(match.group(1).replace(",", "")) * CP_PER[match.group(2)]
    return total if parts else None


def first_int(text: str | None) -> int | None:
    match = re.search(r"\d[\d,]*", text or "")
    return int(match.group(0).replace(",", "")) if match else None


def wait_until(condition, timeout: float = 10.0, interval: float = 0.1):
    """Poll a Python callable until it returns something truthy, else return None."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            value = condition()
        except Exception:
            value = None
        if value:
            return value
        time.sleep(interval)
    return None


class Walker:
    """One browser context at one width, logging every control through a Recorder."""

    def __init__(self, browser, base_url: str, width: int, height: int) -> None:
        self.base_url = base_url
        self.width = width
        self.ctx = browser.new_context(viewport={"width": width, "height": height})
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(8000)
        self.rec = lib.Recorder()
        self.rec.attach(self.page)
        # Highest quantity seen per item on any sheet read: proves a row that is
        # absent later was present before.
        self.seen_max: dict[str, int] = {}

    # -- logging ---------------------------------------------------------

    def ck(self, control: str, expected, actual, ok) -> bool:
        self.rec.check(FLOW, self.page.url, f"{control} @{self.width}", expected, actual, bool(ok))
        return bool(ok)

    def section(self, name: str, fn) -> None:
        """Run one section. A crash is recorded as a failed check, not hidden."""
        try:
            fn()
        except Exception as exc:
            self.ck(f"section {name}", "completes", f"{type(exc).__name__}: {exc}"[:300], False)

    # -- navigation ------------------------------------------------------

    def goto(self, path: str, control: str) -> bool:
        resp = self.page.goto(f"{self.base_url}{path}", wait_until="networkidle")
        status = resp.status if resp else None
        return self.ck(control, "2xx/3xx", status, status is not None and 200 <= status < 400)

    def click_nav(self, locator, control: str, expect_path=None) -> bool:
        """Click a link or submit that navigates. Check status and (optionally) the path."""
        with self.page.expect_navigation(wait_until="networkidle") as info:
            locator.click()
        resp = info.value
        status = resp.status if resp else None
        path = self.page.evaluate("location.pathname")
        ok = status is not None and 200 <= status < 400
        if expect_path is not None:
            ok = ok and (
                bool(expect_path.search(path))
                if hasattr(expect_path, "search")
                else path == expect_path
            )
        return self.ck(
            control,
            f"2xx/3xx at {getattr(expect_path, 'pattern', expect_path)}",
            f"{status} {path}",
            ok,
        )

    def menu_open(self) -> bool:
        return bool(self.page.locator("#site-menu.show").count())

    def open_menu(self, control: str) -> bool:
        self.page.locator("a.wm-hamburger").click()
        shown = wait_until(lambda: self.page.locator("#site-menu.show").is_visible())
        return self.ck(control, "side menu visible", "visible" if shown else "hidden", shown)

    def close_menu(self, control: str) -> bool:
        self.page.locator("#site-menu .btn-close").click()
        gone = wait_until(lambda: self.page.locator("#site-menu.show").count() == 0)
        return self.ck(control, "side menu closed", "closed" if gone else "still open", gone)

    def nav_to(self, label: str, expect_path, menu_label: str | None = None) -> bool:
        """Go to a top-level page with the header shortcut, else through the side menu."""
        link = self.page.locator(f'.wm-shortcuts a.wm-shortcut[aria-label="{label}"]')
        if link.count() and link.first.is_visible():
            return self.click_nav(link.first, f'header nav link "{label}"', expect_path)
        menu_label = menu_label or label
        self.open_menu(f'hamburger opens menu for "{menu_label}"')
        return self.click_nav(
            self.page.locator(f'#site-menu a:text-is("{menu_label}")').first,
            f'side menu link "{menu_label}"',
            expect_path,
        )

    # -- reading ---------------------------------------------------------

    def read_sheet(self) -> dict:
        data = self.page.evaluate(SHEET_JS)
        items: dict[str, int | None] = {}
        for row in data["rows"]:
            qty = first_int(row["inline"] if row["inline"] else row["owned"])
            if row["name"] in items and items[row["name"]] is not None and qty is not None:
                items[row["name"]] += qty
            else:
                items[row["name"]] = qty
        for name, qty in items.items():
            if qty is not None:
                self.seen_max[name] = max(self.seen_max.get(name, 0), qty)
        return {"cp": parse_coins(data["coins"]), "coins_text": data["coins"], "items": items}

    def notice(self, title: str):
        return self.page.locator("article.wm-notice").filter(
            has=self.page.get_by_role("link", name=title, exact=True)
        )

    def toast_text(self) -> str:
        found = wait_until(lambda: self.page.locator(".wm-toast .wm-toast-message").count() > 0, 8)
        if not found:
            return ""
        return self.page.locator(".wm-toast .wm-toast-message").first.inner_text().strip()


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


def check_sheet_baseline(w: Walker) -> dict:
    ok = w.nav_to("Character", SHEET_PATH_RE, "My character")
    sheet = w.read_sheet()
    items = sheet["items"]
    w.ck(
        "baseline: Aria's coins, pelts, potions, parchment read from the sheet",
        "coins>0, Wolf pelt=3, Healing potion=2, Parchment=25",
        f"{sheet['coins_text']} pelts={items.get('Wolf pelt')} "
        f"potions={items.get('Healing potion')} parchment={items.get('Parchment')}",
        ok
        and sheet["cp"] is not None
        and items.get("Wolf pelt") == 3
        and items.get("Healing potion") == 2
        and items.get("Parchment") == 25,
    )
    return sheet


def check_board(w: Walker) -> str:
    """Use every control on the quest list. Returns the reward coin text shown for Pelts."""
    page = w.page
    w.nav_to("Quests", BOARD_PATH)
    page.get_by_role("heading", name="Quests", exact=True).first.wait_for()
    w.ck(
        "board heading",
        "Quests",
        page.locator("h1").first.inner_text().strip(),
        "Quests" in page.locator("h1").first.inner_text(),
    )

    pelts, maps, pack = w.notice(PELTS), w.notice(MAPS), w.notice(PACK)
    for title, notice, have_text, bar, ready in (
        (PELTS, pelts, "3 of 3", ("3", "3"), True),
        (MAPS, maps, "25 of 10 sheet", ("25", "10"), True),
        (PACK, pack, "3 of 99", ("3", "99"), False),
    ):
        got_have = notice.locator(".wm-notice-have").first.inner_text().strip()
        bar_el = notice.locator("progress.wm-notice-bar").first
        got_bar = (bar_el.get_attribute("value"), bar_el.get_attribute("max"))
        w.ck(
            f"progress bar: {title}",
            f"{have_text}, value/max {bar}",
            f"{got_have}, {got_bar}",
            got_have == have_text and got_bar == bar,
        )
        stamps = notice.locator(".wm-stamp--ready").count()
        w.ck(
            f"'Ready to turn in' stamp: {title}",
            "present" if ready else "absent",
            stamps,
            (stamps == 1) == ready,
        )

    reward_coin = pelts.locator("dd .coin").first.inner_text().strip()
    reward_dd = pelts.locator("dl dd").first.inner_text()
    w.ck(
        f"reward text: {PELTS}",
        "1000 cp shown as coins plus Healing potion",
        f"{reward_dd!r} ({parse_coins([reward_coin])} cp)",
        parse_coins([reward_coin]) == 1000 and "Healing potion" in reward_dd,
    )
    maps_coin = maps.locator("dd .coin").first.inner_text().strip()
    w.ck(
        f"reward text: {MAPS}",
        "500 cp",
        f"{maps_coin} ({parse_coins([maps_coin])} cp)",
        parse_coins([maps_coin]) == 500,
    )

    # "Taken down" <details>: click the real summary.
    taken = page.locator("details.wm-taken-down")
    summary = taken.locator("> summary")
    w.ck(
        "'Taken down' present with the ended notice",
        "1 group, 1 notice",
        f"{taken.count()}",
        taken.count() == 1 and summary.inner_text().strip() == "Taken down (1)",
    )
    if taken.count():
        w.ck(
            "'Taken down' starts closed",
            "closed",
            taken.evaluate("el => el.open"),
            not taken.evaluate("el => el.open"),
        )
        summary.click()
        opened = wait_until(lambda: taken.evaluate("el => el.open"))
        shown = page.locator("details.wm-taken-down article.wm-notice").first
        w.ck(
            "'Taken down' click opens",
            "open, shows Old Notice + Ended label",
            f"open={bool(opened)} text={shown.inner_text()[:60]!r}" if opened else "closed",
            opened
            and OLD in shown.inner_text()
            and "Ended" in shown.inner_text()
            and shown.is_visible(),
        )
        summary.click()
        closed = wait_until(lambda: not taken.evaluate("el => el.open"))
        w.ck("'Taken down' click closes", "closed", "closed" if closed else "open", closed)

    # "Preview contents" <details> on the container reward.
    preview = pack.locator("details.wm-loot-stock-preview")
    psummary = preview.locator("> summary")
    w.ck(
        "'Preview contents' present on the pack reward", "1", preview.count(), preview.count() == 1
    )
    if preview.count():
        psummary.click()
        opened = wait_until(lambda: preview.evaluate("el => el.open"))
        rows_visible = preview.locator(".wm-loot-row, li, tr").first
        text = preview.inner_text().replace("\n", " ")[:80]
        w.ck(
            "'Preview contents' click opens",
            "open and rows visible",
            f"open={bool(opened)} {text!r}",
            opened and rows_visible.is_visible() and len(text) > len("Preview contents"),
        )
        psummary.click()
        closed = wait_until(lambda: not preview.evaluate("el => el.open"))
        w.ck("'Preview contents' click closes", "closed", "closed" if closed else "open", closed)

    # Quest title links: open each live quest and come back with "Back to quests".
    for title in (MAPS, PACK):
        w.click_nav(
            w.notice(title).get_by_role("link", name=title, exact=True),
            f"title link: {title}",
            re.compile(r"/c/demo/quests/\d+/$"),
        )
        h1 = page.locator("h1").first.inner_text().strip()
        w.ck(f"detail heading: {title}", title, h1, h1 == title)
        w.click_nav(
            page.get_by_role("link", name="Back to quests"),
            f"'Back to quests' from {title}",
            BOARD_PATH,
        )
        w.ck(
            f"board after back: {title}",
            "board heading",
            page.locator("h1").first.inner_text().strip(),
            page.locator("h1").first.inner_text().strip() == "Quests",
        )
    return reward_coin


def check_pack_detail(w: Walker) -> None:
    """The quest Aria cannot do: pack detail shows a disabled button with a reason."""
    page = w.page
    w.click_nav(
        w.notice(PACK).get_by_role("link", name=PACK, exact=True),
        f"title link: {PACK}",
        re.compile(r"/c/demo/quests/\d+/$"),
    )
    button = page.locator("#turn-in form button[type=submit]")
    reason = (
        page.locator("#turn-in-reason").inner_text().strip()
        if page.locator("#turn-in-reason").count()
        else ""
    )
    w.ck(
        f"turn-in blocked with reason: {PACK}",
        "disabled + 'Missing 96 × Wolf pelt.'",
        f"disabled={button.is_disabled()} {reason!r}",
        button.is_disabled() and reason == "Missing 96 × Wolf pelt.",
    )
    rows = page.locator("#turn-in .wm-reward-list")
    w.ck(
        f"reward preview on detail: {PACK}",
        "reward rows visible",
        rows.inner_text().replace("\n", " ")[:80],
        rows.is_visible() and len(rows.inner_text()) > 10,
    )
    w.click_nav(
        page.get_by_role("link", name="Back to quests"), f"'Back to quests' from {PACK}", BOARD_PATH
    )


def check_pelts_detail(w: Walker) -> None:
    """Detail page before the turn-in: back link, table, rewards, info popup, button."""
    page = w.page
    w.click_nav(
        w.notice(PELTS).get_by_role("link", name=PELTS, exact=True),
        f"title link: {PELTS}",
        re.compile(r"/c/demo/quests/\d+/$"),
    )
    h1 = page.locator("h1").first.inner_text().strip()
    w.ck("detail heading", PELTS, h1, h1 == PELTS)
    w.click_nav(
        page.get_by_role("link", name="Back to quests"), "'Back to quests' link", BOARD_PATH
    )
    w.click_nav(
        w.notice(PELTS).get_by_role("link", name=PELTS, exact=True),
        f"title link again: {PELTS}",
        re.compile(r"/c/demo/quests/\d+/$"),
    )

    row = page.locator("#turn-in tbody tr").first
    cells = [c.inner_text().strip() for c in row.locator("td").all()]
    w.ck(
        "requirements table row",
        "Wolf pelt | 3 | 3 | OK",
        " | ".join(cells),
        len(cells) == 4
        and cells[0].endswith("Wolf pelt")
        and cells[1:3] == ["3", "3"]
        and cells[3] == "OK",
    )
    rewards = page.locator("#turn-in .wm-reward-list").inner_text().replace("\n", " ")
    w.ck(
        "rewards list",
        "10 gp and 1 x Healing potion",
        rewards,
        "10 gp" in rewards and "Healing potion" in rewards,
    )

    # Item info link: a real click opens the app modal, Close dismisses it.
    page.locator("#turn-in a.wm-item-info").first.click()
    opened = wait_until(
        lambda: (
            page.locator("#app-modal.show").count() == 1
            and "Wolf pelt" in page.locator("#app-modal .modal-content").inner_text()
        )
    )
    w.ck(
        "item info link opens modal",
        "modal shows Wolf pelt",
        page.locator("#app-modal .modal-content").inner_text()[:40].replace("\n", " | "),
        opened,
    )
    page.locator("#app-modal .modal-content [data-bs-dismiss=modal]").last.click()
    closed = wait_until(lambda: page.locator("#app-modal.show").count() == 0)
    w.ck("item info modal Close button", "modal closed", "closed" if closed else "open", closed)

    button = page.locator("#turn-in form button[type=submit]")
    w.ck(
        "turn-in button state (Aria)",
        "enabled 'Turn in as Aria Windrunner'",
        f"enabled={button.is_enabled()} {button.inner_text().strip()!r}",
        button.is_enabled() and button.inner_text().strip() == "Turn in as Aria Windrunner",
    )


def switch_character(w: Walker, name: str) -> bool:
    page = w.page
    toggle = page.locator(".character-selector .dropdown-toggle")
    toggle.click()
    menu = page.locator(".character-selector .dropdown-menu")
    shown = wait_until(lambda: menu.is_visible())
    w.ck(
        f"character selector opens (to pick {name})",
        "menu visible with 2 characters",
        f"visible={bool(shown)} items={menu.locator('a[data-character-pk]').count()}",
        shown and menu.locator("a[data-character-pk]").count() == 2,
    )
    option = menu.locator("a[data-character-pk]").filter(has_text=name)
    option.hover()
    tip = wait_until(
        lambda: (
            page.locator(".tooltip.show .tooltip-inner").count()
            and "Loading" not in page.locator(".tooltip.show .tooltip-inner").first.inner_text()
        )
    )
    w.ck(
        f"character preview tooltip on {name}",
        "tooltip with details",
        page.locator(".tooltip.show .tooltip-inner").first.inner_text().replace("\n", " | ")[:70]
        if page.locator(".tooltip.show .tooltip-inner").count()
        else "none",
        tip,
    )
    return w.click_nav(option, f"character switch to {name}", page.evaluate("location.pathname"))


def check_wren(w: Walker) -> None:
    """Switch to Wren on the Pelts detail page: blocked with a reason; board shows no stamp."""
    page = w.page
    switch_character(w, "Wren")
    name = page.locator("#turn-in .wm-quest-turnin-name").inner_text().strip()
    button = page.locator("#turn-in form button[type=submit]")
    reason = (
        page.locator("#turn-in-reason").inner_text().strip()
        if page.locator("#turn-in-reason").count()
        else ""
    )
    w.ck(
        "turn-in blocked for Wren",
        "Wren Thistledown, disabled, 'Missing 3 × Wolf pelt.'",
        f"{name!r} disabled={button.is_disabled()} {reason!r}",
        name.startswith("Wren") and button.is_disabled() and reason == "Missing 3 × Wolf pelt.",
    )
    w.click_nav(
        page.get_by_role("link", name="Back to quests"), "'Back to quests' as Wren", BOARD_PATH
    )
    stamps = w.notice(PELTS).locator(".wm-stamp--ready").count()
    have = w.notice(PELTS).locator(".wm-notice-have").first.inner_text().strip()
    w.ck(
        "board as Wren",
        "no stamp, 0 of 3",
        f"stamps={stamps} {have}",
        stamps == 0 and have == "0 of 3",
    )
    switch_character(w, "Aria")
    stamps = w.notice(PELTS).locator(".wm-stamp--ready").count()
    w.ck(
        "board as Aria again",
        "ready stamp, 3 of 3",
        f"stamps={stamps} {w.notice(PELTS).locator('.wm-notice-have').first.inner_text().strip()}",
        stamps == 1,
    )


def check_header_controls(w: Walker) -> None:
    """Hamburger open and close, on a quest page."""
    page = w.page
    w.open_menu("hamburger (open)")
    links = page.locator("#site-menu a").all_inner_texts()
    w.ck(
        "side menu lists Quests and My character",
        "both links",
        [t.strip() for t in links if t.strip() in ("Quests", "My character")],
        any(t.strip() == "Quests" for t in links)
        and any(t.strip() == "My character" for t in links),
    )
    w.close_menu("side menu close button")


def turn_in(w: Walker, title: str, expect_reward: str, expect_rows: list[str]) -> None:
    """Click the turn-in button on the open detail page, then check toast and celebration."""
    page = w.page
    quest_path = page.evaluate("location.pathname")
    button = page.locator("#turn-in form button[type=submit]")
    w.ck(f"turn-in button enabled: {title}", "enabled", button.is_enabled(), button.is_enabled())
    with page.expect_response(
        lambda r: r.request.method == "POST" and r.url.endswith(quest_path + "turn-in/")
    ) as info:
        button.click()
    status = info.value.status
    w.ck(f"turn-in POST: {title}", "2xx/3xx", status, 200 <= status < 400)
    landed = wait_until(lambda: page.evaluate("location.pathname") == BOARD_PATH, 15)
    page.wait_for_load_state("networkidle")
    w.ck(
        f"turn-in redirects to the board: {title}",
        BOARD_PATH,
        page.evaluate("location.pathname"),
        landed,
    )

    expected_toast = f"✦ Aria Windrunner completed {title}! Reward: {expect_reward}"
    toast = w.toast_text()
    w.ck(f"turn-in toast: {title}", expected_toast, toast, toast == expected_toast)
    if page.locator(".wm-toast-close").count():
        page.locator(".wm-toast-close").first.click()
        gone = wait_until(lambda: page.locator(".wm-toast").count() == 0)
        w.ck("toast dismiss button", "toast removed", "removed" if gone else "still there", gone)

    fan = page.locator("[data-fanfare]")
    w.ck(
        f"celebration shown: {title}",
        f"'Quest complete: {title}' + 'Aria Windrunner turned it in.'",
        fan.inner_text().replace("\n", " ")[:80] if fan.count() else "missing",
        fan.count() == 1
        and f"Quest complete: {title}" in fan.inner_text()
        and "Aria Windrunner turned it in." in fan.inner_text(),
    )
    if not fan.count():
        return
    items = page.locator("[data-wm-reveal-item]")

    def rows_visible() -> bool:
        return items.count() > 0 and all(i.is_visible() for i in items.all())

    def row_labels() -> list[str]:
        return [i.evaluate("e => e.lastChild.textContent.trim()") for i in items.all()]

    # The rewards must end up on screen: the animation settles into a visible row.
    revealed = wait_until(rows_visible, 10)
    w.ck(
        f"celebration reveals the reward rows: {title}",
        "reward rows visible within 10s",
        "visible" if revealed else "hidden (animation never settles)",
        revealed,
    )
    labels = row_labels()
    w.ck(f"celebration reward text: {title}", expect_rows, labels, labels == expect_rows)

    # Replay button replays from the stored data and the rows are visible again.
    page.locator("[data-wm-fanfare-replay]").click()
    again = wait_until(rows_visible, 10)
    w.ck(
        "celebration Replay button",
        "reward rows visible again",
        "visible" if again else "hidden (animation never settles)",
        again,
    )

    # Sound toggle flips aria-pressed and the stored choice.
    sound = page.locator("[data-wm-fanfare-sound]")
    before = sound.get_attribute("aria-pressed")
    sound.click()
    after = sound.get_attribute("aria-pressed")
    stored = page.evaluate("localStorage.getItem('containerFanfareSound')")
    sound.click()
    back = sound.get_attribute("aria-pressed")
    w.ck(
        "celebration sound toggle",
        "false -> true (stored on) -> false",
        f"{before} -> {after} (stored {stored}) -> {back}",
        (before, after, stored, back) == ("false", "true", "on", "false"),
    )


def check_board_after_pelts(w: Walker) -> None:
    pelts = w.notice(PELTS)
    have = pelts.locator(".wm-notice-have").first.inner_text().strip()
    bar = pelts.locator("progress.wm-notice-bar").first
    stamp = pelts.locator(".wm-stamp--ready").count()
    w.ck(
        "board after turn-in: Pelts",
        "0 of 3, bar 0/3, no stamp",
        f"{have}, bar {bar.get_attribute('value')}/{bar.get_attribute('max')}, stamps={stamp}",
        have == "0 of 3" and bar.get_attribute("value") == "0" and stamp == 0,
    )
    maps_stamp = w.notice(MAPS).locator(".wm-stamp--ready").count()
    w.ck("board after turn-in: Maps still ready", "ready stamp", maps_stamp, maps_stamp == 1)


def check_pelts_detail_after(w: Walker) -> None:
    page = w.page
    w.click_nav(
        w.notice(PELTS).get_by_role("link", name=PELTS, exact=True),
        f"title link after turn-in: {PELTS}",
        re.compile(r"/c/demo/quests/\d+/$"),
    )
    row = page.locator("#turn-in tbody tr").first
    cells = [c.inner_text().strip().replace("\n", " ") for c in row.locator("td").all()]
    button = page.locator("#turn-in form button[type=submit]")
    reason = (
        page.locator("#turn-in-reason").inner_text().strip()
        if page.locator("#turn-in-reason").count()
        else ""
    )
    missing_class = "wm-quest-turnin-missing" in (row.get_attribute("class") or "")
    w.ck(
        "detail after turn-in: row says Wolf pelt missing",
        "Wolf pelt | 3 | 0 | Missing 3",
        " | ".join(cells),
        len(cells) == 4
        and cells[0].endswith("Wolf pelt")
        and cells[1:3] == ["3", "0"]
        and cells[3].startswith("Missing")
        and missing_class,
    )
    w.ck(
        "detail after turn-in: button disabled with reason",
        "disabled, 'Missing 3 × Wolf pelt.'",
        f"disabled={button.is_disabled()} {reason!r}",
        button.is_disabled() and reason == "Missing 3 × Wolf pelt.",
    )
    w.click_nav(
        page.get_by_role("link", name="Back to quests"),
        "'Back to quests' after turn-in",
        BOARD_PATH,
    )


def check_reload_and_sheet(
    w: Walker, before: dict, gained_cp: int, deltas: dict[str, tuple[int, str]]
) -> dict:
    """Reload the board (celebration gone), then read the sheet and compare with the baseline.

    ``deltas`` maps item name -> (expected_qty, why). An item row is allowed to be
    absent only when the expected quantity is 0 and the baseline had it.
    """
    page = w.page
    resp = page.reload(wait_until="networkidle")
    status = resp.status if resp else None
    w.ck("board reload", "2xx/3xx", status, status is not None and 200 <= status < 400)
    fanfares = page.locator("[data-fanfare]").count()
    toasts = page.locator(".wm-toast").count()
    w.ck(
        "celebration gone after reload",
        "no fanfare, no toast",
        f"fanfare={fanfares} toast={toasts}",
        fanfares == 0 and toasts == 0,
    )

    ok_nav = w.nav_to("Character", SHEET_PATH_RE, "My character")
    after = w.read_sheet()
    exp_cp = before["cp"] + gained_cp
    w.ck(
        "coins after reload",
        f"{before['cp']} + {gained_cp} = {exp_cp} cp",
        f"{after['cp']} cp ({after['coins_text']})",
        ok_nav and after["cp"] == exp_cp,
    )
    for name, (expected, _why) in deltas.items():
        got = after["items"].get(name)
        was = before["items"].get(name)
        if got is None and expected == 0 and w.seen_max.get(name, 0) > 0:
            w.ck(
                f"inventory after reload: {name}",
                f"0 (earlier sheet showed {w.seen_max[name]})",
                "row gone (0)",
                True,
            )
        else:
            w.ck(f"inventory after reload: {name}", f"{expected} (was {was})", got, got == expected)
    return after


def run_flow(w: Walker) -> None:
    lib.login(w.page, w.base_url, "player")
    w.goto("/c/demo/", "club home")
    w.ck(
        "login as alice",
        "left /accounts/login/",
        w.page.evaluate("location.pathname"),
        "/accounts/login/" not in w.page.evaluate("location.pathname"),
    )

    state: dict = {}
    w.section("baseline sheet", lambda: state.setdefault("base", check_sheet_baseline(w)))
    base = state.get("base")
    if base is None or base["cp"] is None:
        return
    w.section("board", lambda: state.setdefault("reward", check_board(w)))
    w.section("pack detail", lambda: check_pack_detail(w))
    w.section("pelts detail", lambda: check_pelts_detail(w))
    w.section("character switch", lambda: check_wren(w))
    w.section("header controls", lambda: check_header_controls(w))

    reward = state.get("reward") or "10 gp"
    w.section(
        "pelts turn-in",
        lambda: (
            w.click_nav(
                w.notice(PELTS).get_by_role("link", name=PELTS, exact=True),
                "title link before turn-in",
                re.compile(r"/c/demo/quests/\d+/$"),
            ),
            turn_in(w, PELTS, f"{reward}, 1 Healing potion", [reward, "1 Healing potion"]),
            check_board_after_pelts(w),
            check_pelts_detail_after(w),
        ),
    )
    w.section(
        "pelts reload and sheet",
        lambda: state.setdefault(
            "after_pelts",
            check_reload_and_sheet(
                w,
                base,
                1000,
                {
                    "Wolf pelt": (0, "handed in"),
                    "Healing potion": (base["items"]["Healing potion"] + 1, "reward"),
                },
            ),
        ),
    )

    mid = state.get("after_pelts")
    if mid is None:
        return
    w.section("back to board", lambda: w.nav_to("Quests", BOARD_PATH))
    w.section(
        "maps turn-in",
        lambda: (
            w.click_nav(
                w.notice(MAPS).get_by_role("link", name=MAPS, exact=True),
                "title link before turn-in",
                re.compile(r"/c/demo/quests/\d+/$"),
            ),
            turn_in(w, MAPS, "5 gp", ["5 gp"]),
        ),
    )
    w.section(
        "maps reload and sheet",
        lambda: check_reload_and_sheet(
            w,
            mid,
            500,
            {
                "Parchment": (15, "10 handed in"),
                "Wolf pelt": (0, "unchanged"),
                "Healing potion": (mid["items"]["Healing potion"], "unchanged"),
            },
        ),
    )


def run_width(browser, width: int, height: int) -> tuple[int, list[str]]:
    """Fresh DB and server for one width. Returns (controls tried, problems)."""
    with tempfile.TemporaryDirectory(prefix=f"flow3-{width}-") as td:
        env = lib.fresh_demo_db(Path(td) / "demo.sqlite3")
        subprocess.run(
            [sys.executable, "manage.py", "shell", "-c", SEED_EXTRAS],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        with lib.run_server(env) as server:
            w = Walker(browser, server.base_url, width, height)
            try:
                run_flow(w)
            except Exception as exc:
                w.ck("flow", "completes", f"{type(exc).__name__}: {exc}"[:300], False)
            finally:
                w.ctx.close()
            return w.rec.controls_tried, [f"@{width}: {p}" for p in w.rec.problems()]


def main() -> int:
    problems: list[str] = []
    per_width: dict[int, int] = {}
    browser_name = "unknown"
    with sync_playwright() as pw:
        browser, browser_name = lib.launch_browser(pw)
        print(f"Flow 3 quest check: browser={browser_name}")
        try:
            for width, height in ((1280, 800), (390, 844)):
                print(f"--- width {width} ---")
                tried, found = run_width(browser, width, height)
                per_width[width] = tried
                problems.extend(found)
        finally:
            browser.close()

    total = sum(per_width.values())
    counts = ", ".join(f"{w}px={n}" for w, n in per_width.items())
    if problems:
        print(
            f"Flow 3 quest check: PROBLEMS ({len(problems)}), browser={browser_name}, "
            f"controls tried={total} ({counts})"
        )
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"Flow 3 quest check: clean, browser={browser_name}, controls tried={total} ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
