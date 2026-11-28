"""Flow 10: message the admins, then answer it as an admin.

As a player (alice, Aria Windrunner): send a message to the club admins, check
it shows as Open, then check the admin's answer arrives (Handled status, the
grant, the dashboard preview and the coins on the sheet).

As a club admin (gm): open the inbox, find the message, read it, mark it
Handled, and give a 1 gp coin grant. Those admin actions are SETUP only: flow 7
(``flow_7_gm.py``) already checks the status modals, the inbox filters, bulk
Apply and Give. This flow checks only what is new:

* the sent message appears for the player and for the admin;
* the admin outcome (Handled status, the grant) arrives in the player's views;
* the Handled status and the grant survive a reload;
* permissions (a player cannot open the inbox or another player's message);
* the player's "Back to inbox" link, the site admin detail page, and 390 layout.

The product has no reply box and no read/unread mark: the "answer" is a status
change or a grant. Nothing to click for those, so nothing is filed for them.

Runs at 1280 and 390 wide. Each width gets its own fresh seeded demo database
and server (RESEND_API_KEY is stripped, so email is off). Firefox is used if it
launches, else Chromium; the browser name is printed.

Every control is logged through ``Tab.check`` (a visible result, a 2xx/3xx
answer where one is expected, and a clean recorder: no console error, CSP
violation, or 4xx/5xx since the previous check). A missing control is a failed
check, never a skip.

Run: ``python scripts/flow_checks/flow_10_admin_message.py`` (exit 0 clean, 1 on problems).
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

import scripts.flow_check_lib as lib  # noqa: E402

FLOW = "flow_10_admin_message"
CLUB = "/c/demo"
INBOX = f"{CLUB}/accounts/messages/"
FORM = f"{CLUB}/accounts/messages/new/"

MSG_BODY = "Flow 10: can the admins check the goblin cave loot?"
NEEDLE = MSG_BODY[:30]
BOB_BODY = "Flow 10 bob: please look at my map credit."
MSG_LONG = "x" * 2001  # one over the 2000-char model limit
GRANT_GP = 1
CP_PER = {"cp": 1, "sp": 10, "gp": 100, "pp": 1000}

DETAIL_PATH_RE = re.compile(r"/c/demo/accounts/messages/(\d+)/$")
SHEET_PATH_RE = re.compile(r"/c/demo/characters/\d+/$")
CHECKBOX_RE = re.compile(r'name="message_ids"\s+value="(\d+)"')
COINS_RE = re.compile(r"([\d,]+)\s*(pp|gp|sp|cp)\b")

# Seed extras: a second player (bob) with a message of his own, so the
# permission checks use a real message owned by someone else. Plain seed data;
# nothing here gives the admin extra access.
SEED_EXTRAS = """
from accounts.models import Club, Membership, Message
from player_characters.models import Character
club = Club.objects.get(slug="demo")
bob = Membership.objects.get(user__email="bob@example.com", club=club)
brin, _ = Character.objects.get_or_create(club=club, owner=bob, name="Brin Stoneback")
Message.objects.get_or_create(club=club, sender=bob, character=brin,
    body="Flow 10 bob: please look at my map credit.")
"""


# --------------------------------------------------------------------------- pure helpers


def message_pk(row_html: str) -> int | None:
    """Message pk from the tick-box in an inbox row's HTML, else None."""
    match = CHECKBOX_RE.search(row_html or "")
    return int(match.group(1)) if match else None


def detail_pk(path: str) -> int | None:
    """Message pk from a detail page path (``/c/demo/accounts/messages/7/``), else None."""
    match = DETAIL_PATH_RE.search(path or "")
    return int(match.group(1)) if match else None


def rows_matching(texts: list[str], needle: str) -> list[str]:
    """Items from ``texts`` that contain ``needle``."""
    return [t for t in texts if needle in t]


def status_of_badge(text: str) -> str:
    """Normalise a status badge's text ("Handled") to its value ("handled")."""
    return (text or "").strip().lower()


def coins_to_cp(text: str) -> int | None:
    """Copper value of a coin text such as "12 gp 3 sp"; None when there is no coin."""
    parts = COINS_RE.findall(text or "")
    if not parts:
        return None
    return sum(int(n.replace(",", "")) * CP_PER[unit] for n, unit in parts)


# --------------------------------------------------------------------------- Tab


class MissingControl(Exception):
    pass


class Tab:
    """One browser context, one page, its own Recorder."""

    def __init__(self, ctx, base_url: str, label: str, width: int) -> None:
        self.base = base_url
        self.label = label
        self.width = width
        self.page = ctx.new_page()
        self.page.set_default_timeout(8000)
        self.rec = lib.Recorder()
        self.rec.attach(self.page)
        self._mark = 0
        self.problems: list[str] = []
        self.responses: list[tuple[str, int]] = []
        self.page.on("response", lambda r: self.responses.append((r.url, r.status)))

    # -- checks --------------------------------------------------------------

    def check(self, control: str, expected, actual, ok, url=None, expect_problem=None):
        new = self.rec.since(self._mark)
        extra = [p for p in new if not (expect_problem and expect_problem in p)]
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
        if not ok2:
            self.problems.append(f"{control}: expected {expected!r}, got {shown}")
        return ok2

    def flush(self) -> None:
        """Record recorder problems that no check has covered yet (setup steps)."""
        for text in self.rec.since(self._mark):
            self.problems.append(f"unchecked: {text}")
        self._mark = self.rec.mark()

    def wait(self, expr: str, timeout: float = 8) -> bool:
        try:
            lib.poll(self.page, expr, timeout=timeout)
            return True
        except TimeoutError:
            return False

    # -- navigation ----------------------------------------------------------

    def goto(self, path: str, control: str | None = None, expect_status: int = 200):
        """Open a page. ``control`` None means setup only (no check, errors still count)."""
        resp = self.page.goto(f"{self.base}{path}", wait_until="networkidle")
        status = resp.status if resp else None
        if control is not None:
            problem = None if expect_status < 400 else str(expect_status)
            self.check(
                control,
                f"HTTP {expect_status}",
                f"HTTP {status}",
                status == expect_status,
                url=self.page.url,
                expect_problem=problem,
            )
        return status

    def reload(self) -> int | None:
        resp = self.page.reload(wait_until="networkidle")
        return resp.status if resp else None

    def pathname(self) -> str:
        """Current path. Polls: an HTMX swap can replace the document mid-evaluate."""
        end = time.time() + 5
        while True:
            try:
                return self.page.evaluate("location.pathname")
            except Exception:
                if time.time() > end:
                    raise
                time.sleep(0.1)

    def click_through(self, locator, expect_path=None) -> str:
        """Click a link and wait until the page settles on the next path.

        Waits for the path to change (or match ``expect_path``) instead of
        ``expect_navigation``: HTMX boosts some links and a boosted click
        swaps the body without a navigation event.
        """
        before = self.pathname()
        locator.click()
        end = time.time() + 8
        while time.time() < end:
            path = self.pathname()
            done = bool(expect_path.search(path)) if expect_path is not None else path != before
            if done:
                break
            time.sleep(0.1)
        self.page.wait_for_load_state("networkidle")
        return self.pathname()

    def click_nav(self, locator, control: str, expect_path=None) -> bool:
        path = self.click_through(locator, expect_path)
        ok = bool(expect_path.search(path)) if expect_path is not None else True
        return self.check(
            control, f"lands on {getattr(expect_path, 'pattern', 'next page')}", path, ok
        )

    def status_for(self, path_suffix: str) -> int | None:
        """Latest HTTP status seen for a URL path (any request), else None."""
        for url, status in reversed(self.responses):
            if url.split("?")[0].endswith(path_suffix):
                return status
        return None

    # -- reading -------------------------------------------------------------

    def need(self, selector: str, control: str, timeout: float = 8):
        loc = self.page.locator(selector)
        end = time.time() + timeout
        while loc.count() == 0:
            if time.time() > end:
                self.check(control, "control present", "missing", False)
                raise MissingControl(f"{control}: {selector}")
            time.sleep(0.1)
        return loc.first

    def h2(self) -> str:
        """Text of the first h2 in main; polls like :meth:`pathname`."""
        end = time.time() + 5
        while True:
            try:
                return self.page.evaluate(
                    "(() => { const el = document.querySelector('main h2');"
                    " return el ? el.innerText.trim() : ''; })()"
                )
            except Exception:
                if time.time() > end:
                    raise
                time.sleep(0.1)

    def main_text(self) -> str:
        return self.page.locator("main").first.inner_text()

    def no_hscroll(self, control: str, path: str) -> None:
        """Open ``path`` first, then measure that page."""
        self.goto(path)
        sw, iw = self.page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        self.check(control, f"scrollWidth <= {iw}", f"scrollWidth {sw}", sw <= iw + 1, url=path)

    def inbox_find(self, needle: str) -> tuple[list[str], int | None]:
        """Texts of the inbox rows that contain ``needle``, and the first one's pk."""
        rows = self.page.evaluate(
            "Array.from(document.querySelectorAll('#inbox-list tbody tr'))"
            ".filter(r => r.querySelector('input[name=message_ids]'))"
            ".map(r => [r.innerText, r.innerHTML])"
        )
        texts = rows_matching([text for text, _ in rows], needle)
        pk = next((message_pk(html) for text, html in rows if text in texts), None)
        return texts, pk

    def badge_of(self, scope) -> str:
        """Status value shown by the first badge inside ``scope`` (a locator or selector)."""
        loc = self.page.locator(scope) if isinstance(scope, str) else scope
        badge = loc.locator(".wm-badge, .badge")
        return status_of_badge(badge.first.inner_text()) if badge.count() else ""

    def sheet_coins_cp(self) -> int | None:
        """Open the character sheet from the header (or menu) and read the coin total."""
        link = self.page.locator('.wm-shortcuts a.wm-shortcut[aria-label="Character"]')
        if link.count() and link.first.is_visible():
            self.click_through(link.first, SHEET_PATH_RE)
        else:
            self.page.locator("a.wm-hamburger").click()
            self.wait("!!document.querySelector('#site-menu.show')")
            self.click_through(
                self.page.locator('#site-menu a:text-is("My character")').first, SHEET_PATH_RE
            )
        if not SHEET_PATH_RE.match(self.pathname()):
            return None
        return coins_to_cp(self.page.locator(".wm-sheet-coins-total").first.inner_text())

    # -- modal (setup only) ----------------------------------------------------

    def modal_has(self, text: str, timeout: float = 8) -> bool:
        return self.wait(
            "((document.querySelector('#app-modal.show .modal-content')||{}).innerText||'')"
            f".includes({text!r})",
            timeout,
        )

    def modal_closed(self, timeout: float = 8) -> bool:
        return self.wait("!document.querySelector('#app-modal.show')", timeout)

    def row_action(self, pk: int, label: str, expect_text: str) -> None:
        """Click one inbox row action and wait for its modal. Raises if missing."""
        link = self.page.locator(
            f"#inbox-list tbody tr:has(input[name=message_ids][value='{pk}']) "
            f"a[aria-label='{label}']"
        )
        if link.count() == 0:
            raise MissingControl(f"inbox row #{pk} has no '{label}' action")
        link.first.click()
        if not self.modal_has(expect_text):
            raise MissingControl(f"'{label}' modal did not open")

    def confirm_modal(self) -> None:
        self.page.locator("#app-modal .modal-footer button[type=submit]").first.click()
        if not self.modal_closed():
            raise MissingControl("modal did not close after confirm")

    def set_status(self, pk: int, status_filter: str, label: str, expect_text: str) -> None:
        """Mark handled / reopen through the real status modal (setup, no checks)."""
        self.goto(f"{INBOX}?status={status_filter}&kind=all")
        self.row_action(pk, label, expect_text)
        self.confirm_modal()

    def give_coins(self, pk: int, gp: int) -> None:
        """Give coins through the real Give modal: fill, Review, Confirm (setup, no checks)."""
        self.goto(f"{INBOX}?status=open&kind=all")
        self.row_action(pk, "Give coins", "Give coins")
        self.page.fill("#app-modal input[name=coins_gp]", str(gp))
        self.page.locator("#app-modal button[value=review]").first.click()
        if not self.modal_has("Give this from"):
            raise MissingControl("Give coins Review summary did not show")
        self.page.locator("#app-modal button[name=confirmed]").first.click()
        if not self.modal_closed():
            raise MissingControl("Give coins modal did not close after confirm")


# --------------------------------------------------------------------------- player steps


def player_send_message(p: Tab, state: dict) -> None:
    """Alice opens the dashboard, clicks Message Admins, sends a message."""
    p.goto(f"{CLUB}/", "open club home as Alice")
    state["coins_before"] = p.sheet_coins_cp()
    p.check(
        "sheet shows Aria's coin total before the grant",
        "a coin total",
        state["coins_before"],
        state["coins_before"] is not None,
    )
    p.goto(f"{CLUB}/")

    p.need("a:has-text('Message Admins')", "dashboard 'Message Admins' card link")
    p.click_nav(
        p.page.locator("a:has-text('Message Admins')").first,
        "dashboard card link: Message Admins",
        re.compile(r"/c/demo/accounts/messages/new/$"),
    )

    # Empty body and an over-long body: the browser's own validation blocks the submit.
    for control, body in (("send with empty body", ""), ("send with 2001 chars", MSG_LONG)):
        p.page.fill("textarea[name=body]", body)
        before = p.pathname()
        p.page.locator("#message-form button[type=submit]").click()
        p.page.wait_for_load_state("networkidle")
        after = p.pathname()
        p.check(control, "page stays on the form (no send)", after, after == before)

    p.page.fill("textarea[name=body]", MSG_BODY)
    with p.page.expect_navigation(wait_until="networkidle") as nav:
        p.page.locator("#message-form button[type=submit]").click()
    status = nav.value.status
    flash = p.page.locator(".alert").first.inner_text() if p.page.locator(".alert").count() else ""
    row = p.page.locator("table tbody tr", has_text=NEEDLE)
    p.check(
        "send valid message",
        "2xx, flash 'Message sent', one new Open row",
        f"HTTP {status}, flash {flash[:40]!r}, rows={row.count()}, badge={p.badge_of(row)!r}",
        status < 400 and "Message sent" in flash and row.count() == 1 and p.badge_of(row) == "open",
    )

    status = p.reload()
    row = p.page.locator("table tbody tr", has_text=NEEDLE)
    p.check(
        "sent message survives reload",
        "one row, still Open",
        f"HTTP {status}, rows={row.count()}, badge={p.badge_of(row)!r}",
        status == 200 and row.count() == 1 and p.badge_of(row) == "open",
    )

    p.goto(f"{FORM}?template=loot")
    body = p.page.locator("textarea[name=body]").input_value()
    p.check(
        "?template=loot prefills the body",
        "loot template text with the character name",
        body[:60],
        "Aria Windrunner" in body and "missing" in body,
    )


def player_before_answer(p: Tab, state: dict) -> None:
    """Alice checks her message on the dashboard and its detail page before any answer."""
    p.goto(f"{CLUB}/")
    item = p.page.locator(".list-group-item", has_text=NEEDLE)
    p.check(
        "My Messages card shows the new message as Open",
        "one card row, Open badge, no admin preview",
        f"rows={item.count()} badge={p.badge_of(item)!r}",
        item.count() == 1 and p.badge_of(item) == "open" and "Admin" not in item.first.inner_text(),
    )

    link = item.locator("a", has_text="View Response")
    p.need(".list-group-item a:has-text('View Response')", "card 'View Response' link")
    p.click_nav(link.first, "card link: View Response", DETAIL_PATH_RE)
    state["pk"] = detail_pk(p.pathname())
    p.check("detail page URL carries the message pk", "a pk", state["pk"], state["pk"] is not None)
    text = p.main_text()
    p.check(
        "detail page before the answer",
        "heading 'Your Message', body, Open badge, no Admin Response",
        f"h2={p.h2()!r} body={NEEDLE in text} admin_response={'Admin Response' in text}",
        p.h2() == "Your Message"
        and NEEDLE in text
        and p.badge_of("main") == "open"
        and "Admin Response" not in text,
    )

    # The player's own "Back" link. A player cannot open the inbox.
    back = p.page.locator("a:has-text('Back to inbox')")
    p.check("detail page has a Back link", "one link", back.count(), back.count() == 1)
    p.click_through(back.first)
    path = p.pathname()
    status = p.status_for("/accounts/messages/")
    p.check(
        "player's 'Back to inbox' link leads to a working page",
        "2xx page (not an error page)",
        f"HTTP {status} at {path}",
        status is not None and status < 400,
        expect_problem=str(status) if status and status >= 400 else None,
    )


# --------------------------------------------------------------------------- admin steps


def admin_reads_inbox(a: Tab, state: dict) -> None:
    """The admin opens the inbox from the header, finds Alice's message and reads it."""
    a.goto(f"{CLUB}/")
    inbox_link = a.page.locator('.wm-shortcuts a.wm-shortcut[aria-label="Inbox"]')
    if inbox_link.count() and inbox_link.first.is_visible():
        a.click_nav(inbox_link.first, "header link: Inbox", re.compile(r"/accounts/messages/$"))
    else:
        a.goto(INBOX, "open inbox")

    mine, state["admin_pk"] = a.inbox_find(NEEDLE)
    shows_character = bool(mine) and "Aria Windrunner" in mine[0]
    a.check(
        "inbox row for Alice's message",
        "one row with Alice's pk and her character name",
        f"rows={len(mine)} pk={state['admin_pk']} (player pk {state.get('pk')}) "
        f"character={shows_character}",
        len(mine) == 1 and state["admin_pk"] == state.get("pk") and shows_character,
    )

    # The Status column hides below 576px (see inbox.html `wm-col-optional`).
    hidden = a.page.evaluate(
        "Array.from(document.querySelectorAll('#inbox-list th.wm-col-optional'))"
        ".every(e => e.offsetParent === null)"
    )
    a.check(
        "Status column follows the screen width",
        "hidden at 390, shown at 1280",
        f"hidden={hidden}",
        hidden == (a.width <= 480),
    )

    pk = state["admin_pk"]
    if pk is None:
        raise MissingControl("no pk for Alice's message in the inbox")
    a.goto(f"{INBOX}{pk}/", "admin opens Alice's message detail by URL")
    text = a.main_text()
    a.check(
        "admin detail page shows sender and body",
        "Alice (Aria Windrunner) and the message body",
        f"h2={a.h2()!r}",
        NEEDLE in text and "Aria Windrunner" in text,
    )


def admin_answers(a: Tab, state: dict) -> None:
    """Mark Handled, then give 1 gp. Setup only; the checks are on the outcome."""
    pk = state["pk"]
    a.set_status(pk, "open", "Mark handled", "Mark handled")
    a.goto(f"{INBOX}{pk}/")
    a.reload()
    a.check(
        "Handled status survives a reload (admin detail page)",
        "Handled badge and Admin Response section",
        f"badge={a.badge_of('main')!r} response={'Admin Response' in a.main_text()}",
        a.badge_of("main") == "handled" and "Admin Response" in a.main_text(),
    )

    a.set_status(pk, "handled", "Reopen", "Reopen")
    a.give_coins(pk, GRANT_GP)
    a.goto(f"{INBOX}{pk}/")
    a.reload()
    text = a.main_text()
    cp = coins_to_cp(text.split("Items & Coins Granted")[-1])
    a.check(
        "the grant survives a reload (admin detail page)",
        f"Handled, Items & Coins Granted, {GRANT_GP} gp",
        f"badge={a.badge_of('main')!r} granted_heading={'Items & Coins Granted' in text} cp={cp}",
        a.badge_of("main") == "handled"
        and "Items & Coins Granted" in text
        and cp == GRANT_GP * CP_PER["gp"],
    )


# --------------------------------------------------------------------------- player sees answer


def player_sees_answer(p: Tab, state: dict) -> None:
    """Alice reloads and checks that the admin's answer arrived."""
    p.goto(f"{CLUB}/", "reload club home as Alice")
    item = p.page.locator(".list-group-item", has_text=NEEDLE)
    preview = "Admin response: items/coins granted"
    p.check(
        "dashboard card shows Handled and the admin preview",
        f"Handled badge and {preview!r}",
        f"rows={item.count()} badge={p.badge_of(item)!r}",
        item.count() == 1 and p.badge_of(item) == "handled" and preview in item.first.inner_text(),
    )

    link = item.locator("a", has_text="View Response")
    p.click_nav(link.first, "card link: View Response (after the answer)", DETAIL_PATH_RE)
    text = p.main_text()
    cp = coins_to_cp(text.split("Items & Coins Granted")[-1])
    p.check(
        "detail page shows the admin's answer",
        f"Handled badge, Admin Response, {GRANT_GP} gp granted",
        f"badge={p.badge_of('main')!r} response={'Admin Response' in text} cp={cp}",
        p.badge_of("main") == "handled"
        and "Admin Response" in text
        and cp == GRANT_GP * CP_PER["gp"],
    )

    p.goto(FORM, "open the message form again")
    row = p.page.locator("table tbody tr", has_text=NEEDLE)
    p.check(
        "'Your messages' table shows Handled",
        "one row with the Handled badge",
        f"rows={row.count()} badge={p.badge_of(row)!r}",
        row.count() == 1 and p.badge_of(row) == "handled",
    )

    p.goto(f"{CLUB}/")
    after = p.sheet_coins_cp()
    before = state.get("coins_before")
    p.check(
        f"sheet coin total rose by {GRANT_GP} gp",
        f"{before} cp + {GRANT_GP * CP_PER['gp']} cp"
        if before is not None
        else "a coin total before and after",
        after,
        before is not None and after == before + GRANT_GP * CP_PER["gp"],
    )


# --------------------------------------------------------------------------- permissions


def check_permissions(p: Tab, a: Tab, site: Tab, state: dict) -> None:
    """A player cannot open the inbox or another player's message."""
    a.goto(f"{INBOX}?status=all&kind=all")
    bob_rows, bob_pk = a.inbox_find(BOB_BODY[:25])
    a.check("admin finds bob's message in the inbox", "one row", len(bob_rows), bob_pk is not None)
    if bob_pk is None:
        raise MissingControl("bob's message is not in the inbox")
    a.goto(f"{INBOX}{bob_pk}/", "admin opens bob's message detail")

    status = p.goto(INBOX, "Alice opens the admin inbox", expect_status=403)
    shown = p.page.locator("body").inner_text()
    p.check(
        "the inbox stays closed to a player",
        "HTTP 403 and no message list",
        f"HTTP {status}, list={p.page.locator('#inbox-list').count()}, "
        f"body_shown={NEEDLE in shown}",
        status == 403 and p.page.locator("#inbox-list").count() == 0 and NEEDLE not in shown,
    )

    status = p.goto(f"{INBOX}{bob_pk}/", "Alice opens bob's message detail", expect_status=404)
    shown = p.page.locator("body").inner_text()
    p.check(
        "another player's message stays closed",
        "HTTP 404 and bob's text not shown",
        f"HTTP {status}, bob_text_shown={BOB_BODY[:25] in shown}",
        status == 404 and BOB_BODY[:25] not in shown,
    )

    # A site admin has no club membership. The detail view reads membership.id.
    site.goto(f"{INBOX}{state['pk']}/")
    status = site.status_for(f"{INBOX}{state['pk']}/")
    site.check(
        "site admin (no club membership) opens a message detail",
        "HTTP 200",
        f"HTTP {status}",
        status == 200,
        expect_problem="500" if status == 500 else None,
    )


# --------------------------------------------------------------------------- layout at 390


def layout_390(p: Tab, a: Tab, state: dict) -> None:
    """Open each page first, then measure that page."""
    pk = state["pk"]
    p.no_hscroll("message form: no horizontal scroll", FORM)
    p.no_hscroll("message detail (player): no horizontal scroll", f"{INBOX}{pk}/")
    p.no_hscroll("dashboard My Messages card: no horizontal scroll", f"{CLUB}/")
    a.no_hscroll("inbox: no horizontal scroll", INBOX)
    a.no_hscroll("message detail (admin): no horizontal scroll", f"{INBOX}{pk}/")


# --------------------------------------------------------------------------- runner


def section(tab: Tab, name: str, fn, *args) -> None:
    """Run one section. A crash is recorded as a failed check, not hidden."""
    try:
        fn(*args)
    except Exception as exc:
        tab.check(f"section '{name}'", "completes", f"{type(exc).__name__}: {exc}"[:200], False)
        traceback.print_exc(limit=3)


def run_width(browser, width: int, height: int) -> tuple[int, list[str]]:
    """Fresh DB and server for one width. Returns (controls tried, problems)."""
    with tempfile.TemporaryDirectory(prefix=f"flow10-{width}-") as td:
        env = lib.fresh_demo_db(Path(td) / "demo.sqlite3")
        subprocess.run(
            [sys.executable, "manage.py", "shell", "-c", SEED_EXTRAS],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with lib.run_server(env) as server:
            ctxs = [
                browser.new_context(viewport={"width": width, "height": height}) for _ in range(3)
            ]
            try:
                player = Tab(ctxs[0], server.base_url, "player", width)
                admin = Tab(ctxs[1], server.base_url, "admin", width)
                site = Tab(ctxs[2], server.base_url, "site admin", width)
                lib.login(player.page, server.base_url, "player")
                lib.login(admin.page, server.base_url, "gm")
                lib.login(site.page, server.base_url, "admin")

                state: dict = {}
                section(player, "player sends", player_send_message, player, state)
                section(player, "player before answer", player_before_answer, player, state)
                section(admin, "admin reads inbox", admin_reads_inbox, admin, state)
                section(admin, "admin answers", admin_answers, admin, state)
                section(player, "player sees answer", player_sees_answer, player, state)
                section(player, "permissions", check_permissions, player, admin, site, state)
                if width <= 480:
                    section(player, "layout 390", layout_390, player, admin, state)

                tabs = (player, admin, site)
                for t in tabs:
                    t.flush()
                problems = [f"[{t.label}] {x}" for t in tabs for x in t.problems]
                return sum(t.rec.controls_tried for t in tabs), problems
            finally:
                for ctx in ctxs:
                    ctx.close()


def main() -> int:
    problems: list[str] = []
    per_width: dict[int, int] = {}
    browser_name = "unknown"
    with sync_playwright() as pw:
        browser, browser_name = lib.launch_browser(pw)
        print(f"Flow 10 admin message check: browser={browser_name}")
        try:
            for width, height in ((1280, 800), (390, 844)):
                print(f"--- width {width} ---")
                try:
                    tried, found = run_width(browser, width, height)
                    per_width[width] = tried
                    problems.extend(f"[{width}] {x}" for x in found)
                except Exception as exc:
                    traceback.print_exc()
                    per_width[width] = 0
                    problems.append(f"[{width}] run crashed: {exc}")
        finally:
            browser.close()

    total = sum(per_width.values())
    counts = ", ".join(f"{w}px={n}" for w, n in per_width.items())
    if problems:
        print(
            f"Flow 10 admin message check: PROBLEMS ({len(problems)}), browser={browser_name}, "
            f"controls tried={total} ({counts})"
        )
        for x in problems:
            print(f"  {x}")
        return 1
    print(
        f"Flow 10 admin message check: clean, browser={browser_name}, "
        f"controls tried={total} ({counts})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
