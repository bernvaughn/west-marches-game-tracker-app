#!/usr/bin/env python
"""Flow 7: game master click check.

A player (alice, Aria Windrunner) sends a message and a stock request. The game
master (gm) then works the inbox (filters, row status, bulk status, loot give,
starting-equipment approval, stock approval), the agent pages (batch edit,
confirm, discard, proposed item approve/reject, connection create/revoke), the
player-items review page and the ledger. Last, the player reloads and must see
the result (message status, coins, items, ledger).

Every control is a ``Recorder.check``: it needs the visible result, a 2xx/3xx
answer and a clean recorder (no console error, CSP violation, page error or
4xx/5xx since the previous check). A missing control is a failed check, never a
skip. Each width (1280 and 390) gets its own fresh demo database and server.

Uses scripts/flow_check_lib.py. Run: python scripts/flow_checks/flow_7_gm.py
Prints the browser, the controls count per width and any problems. Exit 1 on a
problem.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.flow_check_lib import (  # noqa: E402
    Recorder,
    fresh_demo_db,
    launch_browser,
    login,
    poll,
    run_server,
)

FLOW = "flow-7-gm"
CLUB = "/c/demo"

# Seed rows the demo seed does not have: a second pending batch (to discard) and a
# second pending proposed item (to reject). Written to the throwaway database only.
SEED_EXTRA = """
import datetime
from accounts.models import Club, User
from agent_access.models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine
from player_characters.models import Character
club = Club.objects.get(slug="demo")
conn = AgentConnection.objects.filter(club=club).first()
gm = User.objects.get(email="gm@example.com")
batch = ProposedBatch.objects.create(
    club=club, connection=conn, user=gm, idempotency_key="flow7-discard",
    date=datetime.date.today(), source_notes="Flow 7 batch to discard",
)
wren = Character.objects.get(club=club, name="Wren Thistledown")
ProposedLine.objects.create(batch=batch, character=wren, coins=100, note="Flow 7 discard me")
ProposedItem.objects.create(
    club=club, connection=conn, name="Flow 7 cursed ring",
    status=ProposedItem.Status.PENDING, value_cp=100, description="Reject me",
)
"""

MSG_SEEDED = "silver ring from the goblin cave"
MSG_PLAYER = "Flow 7 message: the goblin chief dropped a jade charm"
STOCK_SEEDED = "super cool armor"
STOCK_PLAYER = "Flow 7 stock request: please stock a mithral shirt"
STARTING = "Moonstone amulet"

COIN_RE = re.compile(r"COINS\s*([\d,]+) gp", re.I)


class Tab:
    """A page, its recorder and a check helper that folds in the recorder state."""

    def __init__(self, ctx, base_url: str, label: str, width: int):
        self.base = base_url
        self.label = label
        self.width = width
        self.page = ctx.new_page()
        self.page.set_default_timeout(8000)
        self.rec = Recorder(self.page)
        self._mark = 0
        self.allowed: list[str] = []  # substrings of expected problems (deliberate 4xx)
        self.page.on(
            "pageerror",
            lambda e: print(f"  page error at {self.page.url}: {e}\n{getattr(e, 'stack', '')}"),
        )

    # -- results -------------------------------------------------------------
    def check(self, control, expected, actual, ok, url=None, expect_problem=None):
        """Log one control. Fails when ``ok`` is false or the recorder logged a problem
        since the previous check (unless it matches ``expect_problem``)."""
        new = self.rec.since(self._mark)
        extra = []
        for problem in new:
            if expect_problem and expect_problem in problem:
                continue
            if any(a in problem for a in self.allowed):
                continue
            extra.append(problem)
        ok2 = bool(ok) and not extra
        shown = str(actual)
        if extra:
            shown += f" | recorder: {extra}"
        self.rec.check(
            FLOW,
            url or self.page.url,
            f"[{self.width}] {self.label}: {control}",
            expected,
            actual=shown,
            ok=ok2,
        )
        self._mark = self.rec.mark()
        return ok2

    # -- waiting -------------------------------------------------------------
    def wait(self, expr: str, timeout: float = 8) -> bool:
        try:
            poll(self.page, expr, timeout=timeout)
            return True
        except TimeoutError:
            return False

    def go(self, path: str, control: str | None = None, expect_status: int = 200):
        """Navigate, check the HTTP status and report it as a control."""
        resp = self.page.goto(f"{self.base}{path}", wait_until="networkidle")
        status = resp.status if resp else None
        ok = status == expect_status
        problem = None if expect_status < 400 else str(expect_status)
        self.check(
            control or f"open {path}",
            f"HTTP {expect_status}",
            f"HTTP {status}",
            ok,
            url=self.page.url,
            expect_problem=problem,
        )
        return status

    def text(self, selector="main") -> str:
        return self.page.locator(selector).first.inner_text()

    def count(self, selector: str) -> int:
        return self.page.locator(selector).count()

    def need(self, selector: str, control: str, timeout: float = 8):
        """Locator for a control that must exist. A missing control is a failed check."""
        loc = self.page.locator(selector)
        end = time.time() + timeout
        while loc.count() == 0:
            if time.time() > end:
                self.check(control, "control present", "missing", False)
                raise MissingControl(f"{control}: {selector}")
            time.sleep(0.1)
        return loc.first

    def no_hscroll(self, control: str):
        """No horizontal scroll at the current width."""
        sw, iw = self.page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        self.check(control, f"scrollWidth <= {iw}", f"scrollWidth {sw}", sw <= iw + 1)

    # -- shared modal --------------------------------------------------------
    def modal_open(self) -> bool:
        return self.wait("!!document.querySelector('#app-modal.show .modal-content .modal-body')")

    def modal_closed(self) -> bool:
        return self.wait("!document.querySelector('#app-modal.show')")

    def modal_has(self, text: str, timeout: float = 8) -> bool:
        return self.wait(
            "((document.querySelector('#app-modal.show .modal-content')||{}).innerText||'')"
            f".includes({json.dumps(text)})",
            timeout,
        )

    def modal_text(self) -> str:
        return self.page.locator("#app-modal .modal-content").first.inner_text()


class MissingControl(Exception):
    pass


def money(text: str) -> int | None:
    m = COIN_RE.search(text)
    return int(m.group(1).replace(",", "")) if m else None


# --------------------------------------------------------------------------- inbox helpers
def inbox_rows(tab: Tab) -> list[str]:
    """Text of every message row in the inbox list (no empty-state row)."""
    return tab.page.evaluate(
        "Array.from(document.querySelectorAll('#inbox-list tbody tr'))"
        ".filter(r => r.querySelector('input[name=message_ids]')).map(r => r.textContent)"
    )


def row_has(tab: Tab, needle: str) -> bool:
    return any(needle in t for t in inbox_rows(tab))


def row_badge(tab: Tab, needle: str) -> str | None:
    """Text of the first visible status badge in the row that holds ``needle``."""
    return tab.page.evaluate(
        """(needle) => {
          const row = Array.from(document.querySelectorAll('#inbox-list tbody tr'))
            .find(r => r.querySelector('input[name=message_ids]') && r.textContent.includes(needle));
          if (!row) return null;
          const b = Array.from(row.querySelectorAll('.wm-badge'))
            .find(e => e.offsetParent !== null && /^(Open|Handled|Closed)$/.test(e.textContent.trim()));
          return b ? b.textContent.trim() : '(no visible badge)';
        }""",
        needle,
    )


ROWS_JS = (
    "Array.from(document.querySelectorAll('#inbox-list tbody tr'))"
    ".filter(r => r.querySelector('input[name=message_ids]'))"
)


def row_gone(g: Tab, needle: str) -> bool:
    """Wait until the list no longer holds a row with ``needle`` (the list refreshed)."""
    return g.wait(f"!{ROWS_JS}.some(r => r.textContent.includes({json.dumps(needle)}))")


def granted_has(g: Tab, text: str) -> bool:
    """Wait until a row's Granted list holds ``text``."""
    return g.wait(
        "Array.from(document.querySelectorAll('#inbox-list .wm-granted'))"
        f".some(e => e.textContent.includes({json.dumps(text)}))"
    )


def badges_are(g: Tab, needles, badge: str) -> bool:
    """Wait until every row that holds one of ``needles`` shows ``badge``."""
    keys = json.dumps(list(needles))
    return g.wait(
        f"{keys}.every(k => {ROWS_JS}.some(r => r.textContent.includes(k) && "
        f"Array.from(r.querySelectorAll('.wm-badge')).some(b => b.textContent.trim() === {json.dumps(badge)})))"
    )


def all_rows_open(g: Tab) -> bool:
    """Wait until every row shows Open and no row stays ticked."""
    return g.wait(
        f"{ROWS_JS}.length > 0 && {ROWS_JS}.every(r => "
        "Array.from(r.querySelectorAll('.wm-badge')).some(b => b.textContent.trim() === 'Open'))"
        " && document.querySelectorAll('#inbox-list input[name=message_ids]:checked').length === 0"
    )


def row_loc(tab: Tab, needle: str):
    return tab.page.locator("#inbox-list tbody tr").filter(
        has=tab.page.locator("input[name=message_ids]"), has_text=needle
    )


def goto_inbox(tab: Tab, status="open", kind="all", control=None):
    tab.go(
        f"{CLUB}/accounts/messages/?status={status}&kind={kind}",
        control or f"open inbox status={status} kind={kind}",
    )
    tab.wait("!!document.querySelector('#inbox-list')")


def click_filter(tab: Tab, nav_label: str, text: str, expected_rows: int | None, control: str):
    link = tab.need(f"nav[aria-label='{nav_label}'] a:text-is('{text}')", control)
    link.click()
    tab.page.wait_for_load_state("networkidle")
    active = tab.page.locator(
        f"nav[aria-label='{nav_label}'] a[aria-current=page]"
    ).first.inner_text()
    rows = len(inbox_rows(tab))
    ok = active == text and (expected_rows is None or rows == expected_rows)
    tab.check(
        control,
        f"pill '{text}' active, {expected_rows} rows",
        f"active '{active}', {rows} rows, url {tab.page.url.split('messages/')[-1]}",
        ok,
    )


def status_modal(tab: Tab, needle: str, label: str, *, confirm: bool, control: str):
    """Open the status modal for the row, then Cancel or confirm. Check the modal text."""
    btn = row_loc(tab, needle).locator(f"a[aria-label='{label}']")
    if btn.count() == 0:
        tab.check(f"{control} button", f"'{label}' button on the row", "missing", False)
        raise MissingControl(control)
    btn.first.click()
    opened = tab.modal_open() and tab.modal_has(label)
    sender_ok = "Alice" in tab.modal_text() or "Bob" in tab.modal_text()
    tab.check(
        f"{control}: modal opens",
        f"modal '{label}' with the sender",
        tab.modal_text()[:70],
        opened and sender_ok,
    )
    if confirm:
        tab.page.locator("#app-modal .modal-footer button[type=submit]").first.click()
    else:
        tab.page.locator("#app-modal .modal-footer button[data-bs-dismiss=modal]").first.click()
    closed = tab.modal_closed()
    tab.check(
        f"{control}: {'confirm' if confirm else 'Cancel'} closes the modal",
        "modal closed",
        "closed" if closed else "still open",
        closed,
    )


# --------------------------------------------------------------------------- player steps
def player_message(p: Tab):
    p.go(f"{CLUB}/accounts/messages/new/", "open message form")
    seeded_row = MSG_SEEDED in p.text()
    p.check(
        "own message list shows the seeded message", "row 'Open' + text", seeded_row, seeded_row
    )
    templates = {
        "loot": "is missing:",
        "map": "as having visited/found:",
        "shop": "start carrying",
    }
    for key, frag in templates.items():
        p.need(f"button[data-template={key}]", f"template button {key}").click()
        value = p.page.locator("textarea[name=body]").input_value()
        ok = frag in value and (key == "shop" or "Aria Windrunner" in value)
        p.check(f"template '{key}' fills the body", f"body contains '{frag}'", value[:60], ok)
    p.need("button[data-template=other]", "template button other").click()
    value = p.page.locator("textarea[name=body]").input_value()
    p.check("template 'other' clears the body", "empty body", repr(value), value == "")
    p.page.fill("textarea[name=body]", MSG_PLAYER)
    with p.page.expect_navigation(wait_until="networkidle") as nav:
        p.page.locator("#message-form button[type=submit]").click()
    status = nav.value.status
    flash = p.text(".alert") if p.count(".alert") else ""
    row = MSG_PLAYER in p.text()
    p.check(
        "Send message",
        "2xx, flash 'Message sent', new Open row",
        f"HTTP {status}, flash {flash[:40]!r}, row {row}",
        status < 400 and "Message sent" in flash and row and "Open" in p.text(),
    )


def player_stock(p: Tab):
    p.go(f"{CLUB}/accounts/messages/stock/new/", "open stock form")
    seeded = STOCK_SEEDED in p.text()
    p.check("own stock request list shows the seeded request", "seeded request row", seeded, seeded)
    # The form carries a 'Template' dropdown. It must do something (fill the body).
    sel = p.page.locator("select[name=template]")
    has_template = sel.count() > 0
    if has_template:
        sel.first.select_option("loot")
        body_after = p.page.locator("textarea[name=body]").input_value()
        p.check(
            "'Template' dropdown fills the request",
            "choosing a template changes the request text",
            f"body after choosing 'Loot correction': {body_after!r}",
            body_after != "",
        )
    p.page.fill("textarea[name=body]", STOCK_PLAYER)
    with p.page.expect_navigation(wait_until="networkidle") as nav:
        p.page.locator("form.wm-form button[type=submit]").click()
    status = nav.value.status
    flash = p.text(".alert") if p.count(".alert") else ""
    p.check(
        "Send stock request",
        "2xx, flash 'Stock request sent', new Open row",
        f"HTTP {status}, flash {flash[:40]!r}",
        status < 400 and "Stock request sent" in flash and STOCK_PLAYER in p.text(),
    )


def player_before(p: Tab) -> dict:
    """Coins before the GM works, read from the sheet."""
    p.go(f"{CLUB}/characters/1/", "open Aria's sheet (before)")
    coins = money(p.text())
    p.check("sheet shows coins", "a coin total", coins, coins is not None)
    return {"coins": coins}


# --------------------------------------------------------------------------- GM inbox
def gm_inbox_filters(g: Tab):
    goto_inbox(g, "open", "all", "open inbox")
    n = len(inbox_rows(g))
    g.check("default Open list", "5 open rows (3 seeded + 2 sent)", n, n == 5)
    click_filter(g, "Filter by status", "Handled", 0, "status pill Handled")
    click_filter(g, "Filter by status", "Closed", 0, "status pill Closed")
    click_filter(g, "Filter by status", "All", 5, "status pill All")
    click_filter(g, "Filter by status", "Open", 5, "status pill Open")
    click_filter(g, "Filter by kind", "Messages", 2, "kind pill Messages")
    click_filter(g, "Filter by kind", "Stock requests", 2, "kind pill Stock requests")
    click_filter(g, "Filter by kind", "Starting requests", 1, "kind pill Starting requests")
    click_filter(g, "Filter by kind", "All", 5, "kind pill All")
    # Row content: the sender and the message the player sent.
    ok = row_has(g, MSG_PLAYER) and row_has(g, STOCK_PLAYER)
    g.check("player's new message and stock request are in the inbox", "both rows present", ok, ok)


def gm_inbox_row_status(g: Tab):
    """Mark handled / Close / Reopen on the player's message through the modal."""
    goto_inbox(g, "open", "all", "open inbox (Open)")
    # Cancel keeps the row.
    status_modal(g, MSG_PLAYER, "Mark handled", confirm=False, control="Mark handled")
    still = row_badge(g, MSG_PLAYER)
    g.check("Cancel leaves the message Open", "badge Open", still, still == "Open")
    # Confirm marks handled; the list refreshes and the row leaves Open.
    status_modal(g, MSG_PLAYER, "Mark handled", confirm=True, control="Mark handled")
    gone = row_gone(g, MSG_PLAYER)
    g.check(
        "Mark handled removes the row from the Open list",
        "row gone, list refreshed",
        f"gone={gone}",
        gone,
    )
    goto_inbox(g, "handled", "all", "open Handled list")
    badge = row_badge(g, MSG_PLAYER)
    g.check(
        "handled message shows in Handled with badge", "badge Handled", badge, badge == "Handled"
    )
    # Reopen.
    status_modal(g, MSG_PLAYER, "Reopen", confirm=True, control="Reopen")
    gone = row_gone(g, MSG_PLAYER)
    g.check("Reopen removes the row from the Handled list", "row gone", f"gone={gone}", gone)
    goto_inbox(g, "open", "all", "open Open list again")
    badge = row_badge(g, MSG_PLAYER)
    g.check("reopened message is Open again", "badge Open", badge, badge == "Open")
    # Close.
    status_modal(g, MSG_PLAYER, "Close", confirm=True, control="Close")
    row_gone(g, MSG_PLAYER)
    goto_inbox(g, "closed", "all", "open Closed list")
    badge = row_badge(g, MSG_PLAYER)
    g.check("closed message shows in Closed with badge", "badge Closed", badge, badge == "Closed")
    status_modal(g, MSG_PLAYER, "Reopen", confirm=True, control="Reopen from Closed")
    row_gone(g, MSG_PLAYER)


def tick_all(g: Tab):
    """Click Select all. It stays ticked after a refresh, so untick it first."""
    box = g.page.locator("#inbox-select-all")
    box.uncheck()
    box.check()


def gm_inbox_bulk(g: Tab):
    goto_inbox(g, "all", "all", "open inbox (All) for bulk")
    # Apply with nothing ticked: the user must get a clear answer, not a silent 400.
    with g.page.expect_response(lambda r: "bulk-status" in r.url) as resp:
        g.page.locator("#inbox-bulk-form button[type=submit]").click()
    status = resp.value.status
    feedback = g.wait(
        "document.querySelectorAll('.alert, .invalid-feedback, [role=alert], .toast').length > 0"
        " || document.querySelector('#inbox-bulk-form input[name=message_ids]:invalid') !== null",
        timeout=2,
    )
    # The 400 also logs a console error a moment later; take it into this check.
    end = time.time() + 3
    while time.time() < end and not any("console error" in x for x in g.rec.since(g._mark)):
        time.sleep(0.1)
    g.check(
        "Apply with nothing ticked",
        "no HTTP error and a visible message telling the GM to tick a message",
        f"HTTP {status}, visible feedback={feedback}",
        status < 400 and feedback,
        expect_problem="400",
    )
    # Tick two rows, Close them in bulk.
    for needle in (MSG_PLAYER, STOCK_SEEDED):
        row_loc(g, needle).locator("input[name=message_ids]").check()
    ticked = g.page.locator("input[name=message_ids]:checked").count()
    g.check("tick two rows", "2 rows ticked", ticked, ticked == 2)
    g.page.select_option("#inbox-bulk-bar select[name=status]", "closed")
    g.page.locator("#inbox-bulk-form button[type=submit]").click()
    ok = badges_are(g, (MSG_PLAYER, STOCK_SEEDED), "Closed")
    g.check(
        "bulk Close",
        "both rows show Closed",
        f"{row_badge(g, MSG_PLAYER)} / {row_badge(g, STOCK_SEEDED)}",
        ok,
    )
    unticked = g.page.locator("input[name=message_ids]:checked").count() == 0
    g.check("list refresh clears ticks", "no tick remains", unticked, unticked)
    # Select all, Reopen everything.
    g.need("#inbox-select-all", "Select all checkbox")
    tick_all(g)
    n_checked = g.page.locator("input[name=message_ids]:checked").count()
    total = len(inbox_rows(g))
    g.check(
        "Select all ticks every row",
        f"{total} ticked",
        n_checked,
        n_checked == total and total == 5,
    )
    g.page.select_option("#inbox-bulk-bar select[name=status]", "open")
    g.page.locator("#inbox-bulk-form button[type=submit]").click()
    ok = all_rows_open(g)
    g.check(
        "bulk Reopen with Select all",
        "all five rows Open",
        f"{[row_badge(g, n) for n in (MSG_SEEDED, MSG_PLAYER)]}",
        ok,
    )
    # Mark handled in bulk for the stock seed + player message, then reopen them.
    for needle in (MSG_PLAYER, STOCK_SEEDED):
        row_loc(g, needle).locator("input[name=message_ids]").check()
    g.page.select_option("#inbox-bulk-bar select[name=status]", "handled")
    g.page.locator("#inbox-bulk-form button[type=submit]").click()
    ok = badges_are(g, (MSG_PLAYER, STOCK_SEEDED), "Handled")
    g.check(
        "bulk Mark handled",
        "two rows Handled",
        f"{row_badge(g, MSG_PLAYER)} / {row_badge(g, STOCK_SEEDED)}",
        ok,
    )
    tick_all(g)
    g.page.select_option("#inbox-bulk-bar select[name=status]", "open")
    g.page.locator("#inbox-bulk-form button[type=submit]").click()
    all_rows_open(g)


def gm_inbox_requests(g: Tab):
    """Approve the requests: stock -> Mark handled, starting equipment -> Grant."""
    goto_inbox(g, "open", "all", "open inbox for requests")
    stock = row_loc(g, STOCK_PLAYER)
    gives = stock.locator("a[aria-label^='Give']").count()
    g.check(
        "stock request row has no give buttons (by design)", "0 give buttons", gives, gives == 0
    )
    status_modal(g, STOCK_PLAYER, "Mark handled", confirm=True, control="approve stock request")
    row_gone(g, STOCK_PLAYER)
    goto_inbox(g, "handled", "stock_request", "open Handled stock requests")
    badge = row_badge(g, STOCK_PLAYER)
    g.check("approved stock request is Handled", "badge Handled", badge, badge == "Handled")
    # Starting equipment: Decline modal opens and cancels, then Grant is confirmed.
    goto_inbox(g, "open", "starting_request", "open starting requests")
    row = row_loc(g, STARTING)
    for label, confirm in (("Decline", False), ("Grant", False), ("Grant", True)):
        btn = row.locator(f"a[aria-label='{label}']")
        if btn.count() == 0:
            g.check(f"starting request {label} button", "button present", "missing", False)
            raise MissingControl(label)
        btn.first.click()
        opened = g.modal_open() and STARTING in g.modal_text()
        g.check(
            f"starting request {label}: modal opens",
            f"modal names '{STARTING}'",
            g.modal_text()[:60],
            opened,
        )
        if confirm:
            g.page.locator("#app-modal .modal-footer button[type=submit]").first.click()
        else:
            g.page.locator("#app-modal .modal-footer button[data-bs-dismiss=modal]").first.click()
        closed = g.modal_closed()
        g.check(
            f"starting request {label}: {'confirm' if confirm else 'Cancel'}",
            "modal closes",
            closed,
            closed,
        )
    gone = row_gone(g, STARTING)
    g.check("Grant takes the starting request out of Open", "row gone from Open", gone, gone)
    goto_inbox(g, "handled", "starting_request", "open Handled starting requests")
    present = row_has(g, STARTING)
    g.check(
        "granted starting request is listed as handled",
        "row present under Handled",
        present,
        present,
    )


def open_give(g: Tab, needle: str, label: str):
    btn = row_loc(g, needle).locator(f"a[aria-label='{label}']")
    if btn.count() == 0:
        g.check(f"{label} button", "button on the row", "missing", False)
        raise MissingControl(label)
    btn.first.click()
    ok = g.modal_open() and g.modal_has(label)
    char = g.page.locator("#app-modal select[name=character]").first.input_value()
    g.check(
        f"{label}: modal opens with the sender's character",
        "modal open, Aria (value 1) pre-selected",
        f"{g.modal_text()[:30]!r}, character {char}",
        ok and char == "1",
    )


def batch_text(n: int) -> str:
    """JS that is true once the give modal footer reads 'Batch: n grant(s)'."""
    return (
        "((document.querySelector('#app-modal .modal-footer')||{}).innerText||'')"
        f".includes('Batch: {n} grant')"
    )


def footer(g: Tab, selector: str):
    g.page.locator(f"#app-modal .modal-footer {selector}").first.click()


def fill_coins(g: Tab, gp: str):
    g.page.fill("#app-modal input[name=coins_gp]", gp)


def fill_item(g: Tab, name: str):
    g.page.locator("#app-modal input[type=search]").first.fill(name)
    g.need(f"#app-modal .wm-item-picker-result[data-item-name='{name}']", f"item result {name}").click()
    picked = g.page.locator("#app-modal input[name=items-0-item][type=hidden]").first.input_value()
    g.check(f"item picker selects {name}", "hidden item id set", picked, picked != "")
    g.page.fill("#app-modal input[name=items-0-quantity]", "1")


def fill_map(g: Tab, location: str):
    g.page.locator("#app-modal label[for$='map_kind_1']").first.click()
    g.page.locator("#app-modal select[name=location]").select_option(label=location)


def give(g: Tab, needle: str, label: str, fill, summary_has: list[str], granted: str):
    """Review, then Give. The Review summary must show what is given. If it does not, the
    single-grant path is broken: use the batch path (Add, Review Batch, Give) so the rest
    of the flow still runs."""
    open_give(g, needle, label)
    fill()
    footer(g, "button[value=review]")
    shown = g.modal_has("Give this from") and all(t in g.modal_text() for t in summary_has)
    g.check(
        f"{label}: Review",
        f"summary names {summary_has}",
        g.modal_text().replace("\n", " ")[:160],
        shown,
    )
    if shown:
        footer(g, "button[name=confirmed]")
    else:
        g.page.locator("#app-modal .btn-close").click()
        g.modal_closed()
        open_give(g, needle, label)
        fill()
        footer(g, "button[value=add]")
        g.wait(batch_text(1))
        footer(g, "button[value=review]")
        g.modal_has("Batch Grant Summary")
        footer(g, "button[name=confirmed]")
    closed = g.modal_closed()
    ok = granted_has(g, granted)
    g.check(
        f"{label}: Give",
        f"modal closes, '{granted}' under Granted",
        f"closed={closed} granted={ok}",
        closed and ok,
    )


def gm_inbox_give(g: Tab):
    goto_inbox(g, "all", "message", "open inbox (All, Messages)")
    # Add with no amount: the form must say what is missing.
    open_give(g, MSG_SEEDED, "Give coins")
    footer(g, "button[value=add]")
    ok = g.modal_has("Enter an amount")
    g.check("Give coins: Add with no amount", "error 'Enter an amount'", g.modal_text()[-90:], ok)
    # Cancel keeps everything as it was.
    fill_coins(g, "9")
    footer(g, "button[data-bs-dismiss=modal]")
    closed = g.modal_closed()
    none_granted = "Granted" not in "".join(inbox_rows(g))
    g.check("Give coins: Cancel", "modal closed, nothing granted", closed, closed and none_granted)
    # Single coin grant: 5 gp.
    give(
        g,
        MSG_SEEDED,
        "Give coins",
        lambda: fill_coins(g, "5"),
        ["Aria Windrunner", "5 gp"],
        "Aria Windrunner: 5 gp",
    )
    badge = row_badge(g, MSG_SEEDED)
    g.check("Give coins marks the message handled", "badge Handled", badge, badge == "Handled")
    # Batch on the player's message: two grants of 1 gp make one 2 gp award.
    open_give(g, MSG_PLAYER, "Give coins")
    for n in (1, 2):
        fill_coins(g, "1")
        footer(g, "button[value=add]")
        g.wait(batch_text(n))
    ok = "Batch: 2 grants" in g.modal_text()
    g.check("Give coins: Add another builds a batch", "'Batch: 2 grants'", ok, ok)
    footer(g, "button[value=review]")
    ok = g.modal_has("Batch Grant Summary") and g.modal_text().count("Coins: 1 gp") == 2
    g.check("Give coins: Review Batch", "two '1 gp' lines", g.modal_text()[:150], ok)
    footer(g, "button[value=edit]")
    ok = g.wait("!!document.querySelector('#app-modal input[name=coins_gp]')")
    ok = ok and "Batch: 2 grants" in g.modal_text()
    g.check("Give coins: batch Back returns to the form", "form with 'Batch: 2 grants'", ok, ok)
    if ok:
        footer(g, "button[value=review]")
        g.modal_has("Batch Grant Summary")
    footer(g, "button[name=confirmed]")
    closed = g.modal_closed()
    ok = granted_has(g, "Aria Windrunner: 2 gp")
    g.check("Give coins: confirm the batch", "'Aria Windrunner: 2 gp' under Granted", ok, closed and ok)
    give(
        g,
        MSG_SEEDED,
        "Give items",
        lambda: fill_item(g, "Longsword"),
        ["Longsword"],
        "Aria Windrunner: Longsword",
    )
    give(
        g,
        MSG_SEEDED,
        "Give map credit",
        lambda: fill_map(g, "The Marches \u2013 (0, -2) \u2013 Wolf Den"),
        ["Wolf Den"],
        "Wolf Den",
    )


def gm_layout_390(g: Tab):
    """390 wide only: the inbox collapses to the phone summary and nothing overflows."""
    goto_inbox(g, "all", "all", "open inbox for layout")
    g.no_hscroll("inbox has no horizontal scroll")
    shown = g.page.evaluate(
        "Array.from(document.querySelectorAll('#inbox-list .d-sm-none')).some(e => e.offsetParent !== null)"
    )
    g.check("phone summary block is visible", "d-sm-none visible", shown, shown)
    hidden_cols = g.page.evaluate(
        "Array.from(document.querySelectorAll('#inbox-list td.d-sm-table-cell')).every(e => e.offsetParent === null)"
    )
    g.check("desktop columns are hidden", "d-sm-table-cell hidden", hidden_cols, hidden_cols)
    fits = g.page.evaluate(
        "(() => { const r = document.querySelector('#inbox-bulk-bar').getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth + 1; })()"
    )
    g.check("bulk bar fits the screen", "right edge <= width", fits, fits)
    small = g.page.evaluate(
        "Array.from(document.querySelectorAll('#inbox-list .wm-row-actions .btn')).filter(b => b.offsetParent !== null)"
        ".map(b => { const r = b.getBoundingClientRect(); return Math.min(r.width, r.height); }).filter(s => s < 24).length"
    )
    g.check(
        "row action buttons are tappable", "every button >= 24px", f"{small} smaller", small == 0
    )


def gm_ledger(g: Tab):
    g.go(f"{CLUB}/ledger/", "open club ledger")
    t = g.text()
    ok = "From message #1" in t and "5 gp" in t and "Longsword" in t
    g.check("ledger lists the new awards", "5 gp and Longsword award rows", ok, ok)
    g.page.select_option("form.wm-ledger-filter select[name=character]", label="Aria Windrunner")
    g.page.locator("form.wm-ledger-filter button[type=submit]").click()
    g.page.wait_for_load_state("networkidle")
    t = g.text()
    only_aria = "Borin Stonefist" not in t.split("Downtime points")[0] and "Aria Windrunner" in t
    g.check("filter by character", "only Aria rows, 2xx", g.page.url.split("?")[-1][:60], only_aria)
    g.page.select_option("form.wm-ledger-filter select[name=kind]", label="Purchase")
    g.page.locator("form.wm-ledger-filter button[type=submit]").click()
    g.page.wait_for_load_state("networkidle")
    empty = "No entries match these filters." in g.text()
    g.check("filter by kind Purchase", "empty list", empty, empty)
    g.need("form.wm-ledger-filter a:text-is('Clear')", "ledger Clear link").click()
    g.page.wait_for_load_state("networkidle")
    t = g.text()
    ok = "?" not in g.page.url and "Borin Stonefist" in t and "From message #1" in t
    g.check("Clear resets the filters", "all rows back, no query string", g.page.url, ok)
    g.need("a:text-is('History')", "ledger row History link").click()
    g.page.wait_for_load_state("networkidle")
    ok = "History of" in g.text()
    g.check("History link opens the character history", "'History of ...'", g.page.url, ok)


def gm_player_items(g: Tab):
    g.go(f"{CLUB}/characters/review/", "open player-items review")
    g.page.fill("#id_q", "zzz")
    g.page.locator("form.d-flex button[type=submit]").first.click()
    g.page.wait_for_load_state("networkidle")
    ok = "q=zzz" in g.page.url and "No open player-item groups" in g.text()
    g.check("review Search", "q=zzz in URL, empty state", g.page.url, ok)
    g.need("a:text-is('Clear')", "review Clear link").click()
    g.page.wait_for_load_state("networkidle")
    g.check("review Clear", "q removed", g.page.url, "q=" not in g.page.url)


# --------------------------------------------------------------------------- GM agent pages
def gm_agent(g: Tab):
    g.go(f"{CLUB}/agent/", "open agent access")
    for link, title in (
        ("Connections", "Agent connections"),
        ("Batches", "Agent batches"),
        ("Proposed items", "Proposed items"),
    ):
        g.need(f".wm-agent-link:has(strong:text-is('{link}'))", f"agent card {link}").click()
        g.page.wait_for_load_state("networkidle")
        ok = title in g.text()
        g.check(f"agent card {link}", f"page '{title}'", g.page.url, ok)
        g.go(f"{CLUB}/agent/", "back to agent access")
    # --- batches
    g.go(f"{CLUB}/agent/batches/", "open batches")
    t = g.text()
    g.check(
        "pending batches listed",
        "Batch #1 and #2",
        "Batch #1" in t and "Batch #2" in t,
        "Batch #1" in t and "Batch #2" in t,
    )
    g.need(".wm-agent-batch-card:has-text('Session 1') a.btn", "batch Review button").click()
    g.page.wait_for_load_state("networkidle")
    ok = "/batches/1/" in g.page.url and "Wolf pelt" in g.text()
    g.check("batch Review button", "opens batch #1", g.page.url, ok)
    # edit line 1 (Aria, Wolf pelt): quantity 1 -> 2
    g.need("#edit-line-1 summary", "edit line 1 summary").click()
    g.page.fill("#edit-line-1 input[name=line-1-quantity]", "2")
    g.page.locator("#edit-line-1 button:text-is('Save line')").click()
    g.page.wait_for_load_state("networkidle")
    qty = g.page.locator("#line-1 td.num").nth(1).inner_text().strip()
    g.check("Save line", "line 1 quantity 2", f"quantity cell {qty!r}", qty == "2")
    # remove line 2 (Borin's 5 gp)
    g.need("#edit-line-2 summary", "edit line 2 summary").click()
    g.page.locator("#edit-line-2 button:text-is('Remove line')").click()
    g.page.wait_for_load_state("networkidle")
    removed = g.count("#line-2") == 0
    g.check("Remove line", "line 2 gone", f"line-2 rows: {g.count('#line-2')}", removed)
    # confirm
    g.page.locator("button:has-text('Confirm batch')").click()
    g.page.wait_for_load_state("networkidle")
    t = g.text()
    ok = "Confirmed" in t and g.count("button:has-text('Confirm batch')") == 0
    g.check("Confirm batch", "status Confirmed, confirm button gone", ok, ok)
    g.go(f"{CLUB}/agent/batches/", "open batches after confirm")
    t = g.text()
    recent = t.split("Recent")[-1]
    ok = "Batch #1" in recent and "Confirmed" in recent
    g.check("confirmed batch moves to Recent", "Batch #1 Confirmed under Recent", ok, ok)
    # discard batch 2
    g.go(f"{CLUB}/agent/batches/2/", "open batch #2")
    g.page.locator("button:has-text('Discard batch')").click()
    g.page.wait_for_load_state("networkidle")
    g.go(f"{CLUB}/agent/batches/", "open batches after discard")
    pending = g.text().split("Recent")[0]
    ok = "Batch #2" not in pending
    g.check("Discard batch", "batch #2 no longer pending", ok, ok)
    # --- proposed items
    g.go(f"{CLUB}/agent/proposed-items/", "open proposed items")
    for text, rows in (("Approved", 0), ("Rejected", 0), ("All", 2), ("Pending", 2)):
        g.need(
            f"nav[aria-label='Filter by status'] a:text-is('{text}')", f"proposed items pill {text}"
        ).click()
        g.page.wait_for_load_state("networkidle")
        n = g.count("tbody tr:has(a:text-is('Review'))")
        g.check(f"proposed items pill {text}", f"{rows} rows", n, n == rows)
    g.page.locator("tr:has-text('Frost-touched dagger') a:text-is('Review')").click()
    g.page.wait_for_load_state("networkidle")
    g.page.fill("#id_description", "A pale dagger, cold to the touch. Edited by flow 7.")
    g.page.locator("button:text-is('Save changes')").click()
    g.page.wait_for_load_state("networkidle")
    ok = (
        "Changes saved" in g.text()
        and "Edited by flow 7" in g.page.locator("#id_description").input_value()
    )
    g.check("proposed item Save changes", "flash 'Changes saved', text kept", ok, ok)
    g.page.locator("button.wm-agent-approve").click()
    g.page.wait_for_load_state("networkidle")
    t = g.text()
    ok = "Approved" in t and "Frost-touched dagger" in t and g.count("button.wm-agent-approve") == 0
    g.check("proposed item Approve", "status Approved, in the catalogue", ok, ok)
    g.go(f"{CLUB}/items/", "open item catalogue")
    ok = "Frost-touched dagger" in g.text()
    g.check("approved item is in the catalogue", "'Frost-touched dagger' listed", ok, ok)
    g.go(f"{CLUB}/agent/proposed-items/", "open proposed items for Reject")
    g.page.locator("tr:has-text('Flow 7 cursed ring') a:text-is('Review')").click()
    g.page.wait_for_load_state("networkidle")
    g.page.locator("button:text-is('Reject')").click()
    g.page.wait_for_load_state("networkidle")
    ok = (
        "Proposal rejected" in g.text()
        and "Flow 7 cursed ring" not in g.text().split("Rejected")[0]
    )
    g.check("proposed item Reject", "flash 'Proposal rejected', gone from Pending", ok, ok)
    g.need("nav[aria-label='Filter by status'] a:text-is('Rejected')", "Rejected pill").click()
    g.page.wait_for_load_state("networkidle")
    ok = "Flow 7 cursed ring" in g.text()
    g.check("rejected item shows under Rejected", "ring listed", ok, ok)
    # --- connections
    g.go(f"{CLUB}/agent/connections/", "open connections")
    g.page.fill("#id_label", "Flow 7 token")
    g.page.locator("form:has(#id_label) button[type=submit]").click()
    g.page.wait_for_load_state("networkidle")
    secret = g.count("#new-secret") > 0 and "wm_" in g.text("#new-secret")
    g.check(
        "Create token", "secret shown once, new row", secret and "Flow 7 token" in g.text(), secret
    )
    for label in ("Flow 7 token", "Demo agent"):
        g.page.locator(f"tr:has-text('{label}') button:text-is('Revoke')").click()
        g.page.wait_for_load_state("networkidle")
        ok = (
            g.page.locator(f"tr:has-text('{label}') .wm-badge").first.inner_text().strip()
            == "Revoked"
        )
        g.check(f"Revoke '{label}'", "badge Revoked", ok, ok)


# --------------------------------------------------------------------------- player results
def player_results(p: Tab, before: dict):
    p.go(f"{CLUB}/characters/1/", "reload Aria's sheet (after)")
    t = p.text()
    after = money(t)
    want = before["coins"] + 7
    p.check("sheet coins = before + 5 gp + 2 gp", f"{want} gp", f"{after} gp", after == want)
    p.check(
        "sheet inventory shows the Longsword",
        "'Longsword' on the sheet",
        "Longsword" in t,
        "Longsword" in t,
    )
    p.go(f"{CLUB}/characters/mine/", "open my characters")
    inv_ok = "Longsword" in p.text() or "Longsword" in t
    p.check("player inventory lists Longsword", "'Longsword'", inv_ok, inv_ok)
    p.go(f"{CLUB}/ledger/character/1/", "open Aria's ledger history")
    t = p.text()
    ok = (
        "From message #1" in t
        and "+5 gp" in t
        and "+2 gp" in t
        and "Longsword" in t
        and "+2" in t
        and "Wolf pelt" in t
    )
    p.check(
        "ledger history lists the awards", "+5 gp, +2 gp, Longsword, agent Wolf pelt x2", ok, ok
    )
    p.go(f"{CLUB}/accounts/messages/new/", "reload message list")
    t = p.text()
    sent_ok = MSG_PLAYER in t and MSG_SEEDED in t
    statuses = p.page.evaluate(
        "Array.from(document.querySelectorAll('table tbody tr')).map(r => r.cells[0].textContent.trim() + ' | ' + r.cells[1].textContent.trim().slice(0, 30))"
    )
    handled = all(
        any(s.startswith("Handled") and needle in s for s in statuses)
        for needle in ("the goblin chief", "silver ring")
    )
    p.check(
        "message list shows both messages Handled",
        "Handled for both",
        statuses,
        sent_ok and handled,
    )
    p.go(f"{CLUB}/accounts/messages/stock/new/", "reload stock requests")
    statuses = p.page.evaluate(
        "Array.from(document.querySelectorAll('table tbody tr')).map(r => r.cells[0].textContent.trim() + ' | ' + r.cells[1].textContent.trim().slice(0, 30))"
    )
    ok = any(s.startswith("Handled") and "mithral shirt" in s for s in statuses) and any(
        s.startswith("Open") and "super cool armor" in s for s in statuses
    )
    p.check("stock list shows approved request Handled, other Open", "Handled + Open", statuses, ok)
    p.go(f"{CLUB}/accounts/messages/", "player opens the GM inbox", expect_status=403)
    forbidden = p.page.locator("body").inner_text().strip() != ""
    p.check(
        "GM inbox is not shown to a player",
        "403 with a message, not a blank page",
        forbidden,
        forbidden,
    )


# --------------------------------------------------------------------------- runner
def run_width(browser, width: int, height: int) -> tuple[list[Recorder], list[str]]:
    recs: list[Recorder] = []
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="flow7-") as td:
        env = fresh_demo_db(Path(td) / "demo.sqlite3")
        subprocess.run(
            [sys.executable, "manage.py", "shell", "-c", SEED_EXTRA],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with run_server(env) as server:
            player_ctx = browser.new_context(viewport={"width": width, "height": height})
            gm_ctx = browser.new_context(viewport={"width": width, "height": height})
            try:
                player = Tab(player_ctx, server.base_url, "player", width)
                gm = Tab(gm_ctx, server.base_url, "gm", width)
                recs += [player.rec, gm.rec]
                login(player.page, server.base_url, "player")
                login(gm.page, server.base_url, "gm")
                state: dict = {}

                def section(tab: Tab, name: str, fn, *args):
                    try:
                        fn(*args)
                    except Exception as exc:  # a crash is a failed control, never a skip
                        tab.check(
                            f"section '{name}'",
                            "completes",
                            f"{type(exc).__name__}: {str(exc)[:160]}",
                            False,
                        )
                        traceback.print_exc(limit=3)

                section(player, "player message", player_message, player)
                section(player, "player stock request", player_stock, player)
                try:
                    state = player_before(player)
                except Exception as exc:
                    state = {"coins": 0}
                    player.check("section 'player before'", "completes", str(exc)[:160], False)
                section(gm, "inbox filters", gm_inbox_filters, gm)
                section(gm, "inbox row status", gm_inbox_row_status, gm)
                section(gm, "inbox bulk", gm_inbox_bulk, gm)
                section(gm, "inbox requests", gm_inbox_requests, gm)
                section(gm, "inbox give", gm_inbox_give, gm)
                if width <= 480:
                    section(gm, "layout", gm_layout_390, gm)
                section(gm, "agent", gm_agent, gm)
                section(gm, "player items review", gm_player_items, gm)
                section(gm, "ledger", gm_ledger, gm)
                section(player, "player results", player_results, player, state)
            finally:
                player_ctx.close()
                gm_ctx.close()
    for rec in recs:
        problems += rec.problems()
    return recs, problems


def main(argv: list[str] | None = None) -> int:
    import argparse

    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--widths", default="1280,390", help="comma list, default 1280,390")
    args = parser.parse_args(argv)
    widths = [(int(w), 844 if int(w) <= 480 else 800) for w in args.widths.split(",")]

    all_problems: list[str] = []
    per_width: dict[int, int] = {}
    with sync_playwright() as pw:
        browser, name = launch_browser(pw)
        print(f"flow 7 (game master): browser={name}")
        try:
            for width, height in widths:
                print(f"--- width {width} ---")
                try:
                    recs, problems = run_width(browser, width, height)
                except Exception as exc:
                    traceback.print_exc()
                    per_width[width] = 0
                    all_problems.append(f"[{width}] run crashed: {exc}")
                    continue
                per_width[width] = sum(r.controls_tried for r in recs)
                all_problems += [f"[{width}] {p}" for p in problems]
        finally:
            browser.close()
    total = sum(per_width.values())
    detail = ", ".join(f"{w}px: {n}" for w, n in per_width.items())
    print(f"flow 7 (game master): browser={name}, controls tried {total} ({detail})")
    if all_problems:
        print(f"PROBLEMS ({len(all_problems)}):")
        for problem in all_problems:
            print(f"  {problem}")
        return 1
    print("flow 7 (game master): clean recorder (no console error, CSP violation or 4xx/5xx)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
