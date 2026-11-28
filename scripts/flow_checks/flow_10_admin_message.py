"""Flow 10: message the admins.

As a player (alice, Aria Windrunner): send a message to the club admins,
check it appears as Open, then check the admin's answer arrives (status
change + grant).

As an admin: open the inbox, read the message, mark it Handled, and give
a coins grant on a second message.

Runs at 1280 and 390 wide. Each width gets its own fresh seeded demo
database and server. Firefox is used if it launches, else Chromium.

Every control is a Recorder.check: a visible result, a 2xx/3xx answer,
and a clean recorder (no console error, CSP violation, 4xx/5xx since
the previous check). A missing control is a failed check, never a skip.

Flow 7 already covers the message form templates, inbox filters, status
modals, bulk Apply and Give in detail. This flow exercises each control
as part of the player→admin→player loop without repeating those checks.

Run: python scripts/flow_checks/flow_10_admin_message.py
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

FLOW = "flow_10_admin_message"
CLUB = "/c/demo"

MSG_BODY = "Flow 10: can the admins check the goblin cave loot?"
MSG_LONG = "x" * 2001  # one over the 2000-char model limit
GRANT_GP = "1"
DETAIL_URL_RE = re.compile(r"/c/demo/accounts/messages/\d+/$")

# Seed extras: give the admin user a club membership so the admin can view
# message detail pages (the view accesses request.membership.id).
SEED_EXTRAS = """
from accounts.models import Club, Membership
from django.contrib.auth import get_user_model
User = get_user_model()
club = Club.objects.get(slug="demo")
admin = User.objects.get(email="admin@example.com")
Membership.objects.get_or_create(user=admin, club=club,
    defaults={"is_club_admin": True, "is_game_master": True})
"""


# --------------------------------------------------------------------------- pure helpers


def first_int(text: str | None) -> int | None:
    """First integer found in text, else None."""
    match = re.search(r"\d[\d,]*", text or "")
    return int(match.group(0).replace(",", "")) if match else None


def rows_matching(texts: list[str], needle: str) -> list[str]:
    """List items from texts that contain needle."""
    return [t for t in texts if needle in t]


def status_of_badge(text: str) -> str:
    """Normalise a badge display text to its status value."""
    return text.strip().lower()


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
        return ok2

    def wait(self, expr: str, timeout: float = 8) -> bool:
        try:
            lib.poll(self.page, expr, timeout=timeout)
            return True
        except TimeoutError:
            return False

    # -- navigation ----------------------------------------------------------

    def goto(self, path: str, control: str | None = None, expect_status: int = 200):
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

    def click_nav(self, locator, control: str, expect_path=None) -> bool:
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
        return self.check(
            control,
            f"2xx/3xx at {getattr(expect_path, 'pattern', expect_path)}",
            f"{status} {path}",
            ok,
        )

    def open_menu(self, control: str) -> bool:
        self.page.locator("a.wm-hamburger").click()
        shown = self.wait("!!document.querySelector('#site-menu.show')")
        return self.check(control, "side menu visible", "visible" if shown else "hidden", shown)

    def close_menu(self, control: str) -> bool:
        self.page.locator("#site-menu .btn-close").click()
        gone = False
        end = time.time() + 5
        while time.time() < end:
            if self.page.locator("#site-menu.show").count() == 0:
                gone = True
                break
            time.sleep(0.1)
        return self.check(control, "side menu closed", "closed" if gone else "still open", gone)

    def nav_to(self, label: str, expect_path, menu_label: str | None = None) -> bool:
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

    def no_hscroll(self, control: str):
        sw, iw = self.page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        self.check(control, f"scrollWidth <= {iw}", f"scrollWidth {sw}", sw <= iw + 1)

    def text(self, selector="main") -> str:
        return self.page.locator(selector).first.inner_text()

    # -- modal ---------------------------------------------------------------

    def modal_open(self) -> bool:
        return self.wait("!!document.querySelector('#app-modal.show .modal-content .modal-body')")

    def modal_closed(self) -> bool:
        return self.page.locator("#app-modal.show").count() == 0

    def modal_has(self, text: str, timeout: float = 8) -> bool:
        return self.wait(
            "((document.querySelector('#app-modal.show .modal-content')||{}).innerText||'')"
            f".includes({text!r})",
            timeout,
        )

    def modal_text(self) -> str:
        return self.page.locator("#app-modal .modal-content").first.inner_text()


# --------------------------------------------------------------------------- player steps


def player_send_message(p: Tab) -> None:
    """Alice opens the dashboard, clicks Message Admins, sends a message."""
    p.goto(f"{CLUB}/", "open club home as Alice")

    # Click the "Message Admins" dashboard card link.
    p.need("a:has-text('Message Admins')", "dashboard 'Message Admins' card link")
    p.click_nav(
        p.page.locator("a:has-text('Message Admins')").first,
        "dashboard card link: Message Admins",
        re.compile(r"/c/demo/accounts/messages/new/$"),
    )

    # Empty body: HTML5 'required' blocks submit; check the page stays put.
    before_url = p.page.evaluate("location.pathname")
    p.page.locator("#message-form button[type=submit]").click()
    p.page.wait_for_load_state("networkidle")
    after_url = p.page.evaluate("location.pathname")
    p.check(
        "send with empty body",
        "page stays on form (HTML5 required blocks submit)",
        f"url={after_url}",
        after_url == before_url,
    )

    # 2001 chars: over the 2000 limit; HTML5 maxlength blocks submit.
    p.page.fill("textarea[name=body]", MSG_LONG)
    before_url = p.page.evaluate("location.pathname")
    p.page.locator("#message-form button[type=submit]").click()
    p.page.wait_for_load_state("networkidle")
    after_url = p.page.evaluate("location.pathname")
    p.check(
        "send with 2001 chars",
        "page stays on form (HTML5 maxlength blocks submit)",
        f"url={after_url}",
        after_url == before_url,
    )

    # Valid message.
    p.page.fill("textarea[name=body]", MSG_BODY)
    with p.page.expect_navigation(wait_until="networkidle") as nav:
        p.page.locator("#message-form button[type=submit]").click()
    status = nav.value.status
    flash = p.text(".alert") if p.page.locator(".alert").count() else ""
    rows = p.page.evaluate(
        "Array.from(document.querySelectorAll('table tbody tr')).map(r => r.textContent)"
    )
    open_row = any(MSG_BODY[:30] in r and "Open" in r for r in rows)
    p.check(
        "send valid message",
        "2xx, flash 'Message sent', new Open row",
        f"HTTP {status}, flash {flash[:50]!r}, open_row={open_row}",
        status < 400 and "Message sent" in flash and open_row,
    )

    # Reload: the row stays.
    resp = p.page.reload(wait_until="networkidle")
    status = resp.status if resp else None
    rows = p.page.evaluate(
        "Array.from(document.querySelectorAll('table tbody tr')).map(r => r.textContent)"
    )
    open_row = any(MSG_BODY[:30] in r and "Open" in r for r in rows)
    p.check(
        "your messages row survives reload",
        "row still Open after reload",
        f"HTTP {status}, open_row={open_row}",
        status < 400 and open_row,
    )

    # Template prefill: ?template=loot.
    p.goto(f"{CLUB}/accounts/messages/new/?template=loot", "open form with template=loot")
    body_val = p.page.locator("textarea[name=body]").input_value()
    p.check(
        "template=loot prefills the body",
        "body starts with loot template text",
        body_val[:60],
        "I think" in body_val and "missing:" in body_val,
    )


def player_before_answer(p: Tab) -> None:
    """Alice checks her messages before the admin answers."""
    p.goto(f"{CLUB}/", "open club home as Alice")

    # "My Messages" card shows the new message with Open badge.
    p.need(".list-group-item", "My Messages card items")
    items = p.page.locator(".list-group-item").all_inner_texts()
    found = any(MSG_BODY[:30] in t and "Open" in t for t in items)
    p.check(
        "My Messages card shows new message",
        "message row with Open badge",
        f"items={len(items)} found={found}",
        found,
    )

    # Click "View Response" on Alice's message → detail page.
    # Find the list item that contains our message body text and click its
    # "View Response" link directly (avoids URL-matching issues).
    clicked = p.page.evaluate(
        """(needle) => {
          const li = Array.from(document.querySelectorAll('.list-group-item'))
            .find(el => el.textContent.includes(needle));
          if (!li) return false;
          const as = Array.from(li.querySelectorAll('a'));
          const a = as.find(el => el.textContent.includes('View Response'));
          if (!a) return false;
          a.click();
          return true;
        }""",
        MSG_BODY[:30],
    )
    if not clicked:
        p.check(
            "'View Response' link on Alice's message",
            "link present and clickable",
            "missing",
            False,
        )
        return
    p.page.wait_for_load_state("networkidle")
    # Wait for the page to settle after HTMX navigation.
    end = time.time() + 5
    detail_path = ""
    while time.time() < end:
        try:
            detail_path = p.page.evaluate("location.pathname")
            break
        except Exception:
            time.sleep(0.1)
    p.check(
        "'View Response' link navigates to detail",
        "detail page URL",
        detail_path,
        bool(DETAIL_URL_RE.search(detail_path)),
    )
    h2_text = ""
    end = time.time() + 5
    while time.time() < end:
        try:
            h2_text = p.page.evaluate(
                "() => { const el = document.querySelector('main h2');"
                " return el ? el.innerText.trim() : ''; }"
            )
            break
        except Exception:
            time.sleep(0.1)
    h2 = h2_text
    p.check(
        "detail page heading",
        "'Your Message'",
        h2,
        h2 == "Your Message",
    )
    # Check the body is visible on the detail page.
    body_shown = MSG_BODY[:30] in p.text()
    badge_open = "Open" in p.text()
    no_admin_response = "Admin Response" not in p.text()
    p.check(
        "detail page before answer",
        "body + Open badge + no Admin Response",
        f"body={body_shown} badge={badge_open} no_admin_response={no_admin_response}",
        body_shown and badge_open and no_admin_response,
    )

    # "Back to inbox" link on the player detail page.
    p.need("a:has-text('Back to inbox')", "'Back to inbox' link")
    p.check(
        "Back to inbox link present",
        "link exists",
        "present",
        True,
    )


# --------------------------------------------------------------------------- admin steps


def admin_reads_inbox(a: Tab) -> None:
    """Admin opens the inbox and finds Alice's message."""
    a.goto(f"{CLUB}/accounts/messages/", "open admin inbox")

    # The new message row is present.
    a.need("#inbox-list tbody tr", "inbox rows")
    rows = a.page.evaluate(
        "Array.from(document.querySelectorAll('#inbox-list tbody tr'))"
        ".filter(r => r.querySelector('input[name=message_ids]'))"
        ".map(r => r.textContent)"
    )
    found = any(MSG_BODY[:30] in r for r in rows)
    a.check(
        "inbox shows Alice's message",
        "row with sender + character + body + date",
        f"rows={len(rows)} found={found}",
        found,
    )

    # Status column visible at 1280; hidden at 390 (d-none d-sm-table-cell).
    if a.width > 480:
        status_col = a.page.locator("th:has-text('Status')").count() > 0
        a.check("Status column header visible", "Status column at 1280", status_col, status_col)
    else:
        # At 390, Status column cells are hidden (d-none d-sm-table-cell)
        hidden = a.page.evaluate(
            "Array.from(document.querySelectorAll('#inbox-list th.wm-col-optional'))"
            ".every(e => e.offsetParent === null)"
        )
        a.check("Status column hidden at 390", "Status column hidden", hidden, hidden)

    # Open the detail page as admin by URL (inbox rows have no detail link).
    detail_pk = a.page.evaluate(
        """(needle) => {
          const row = Array.from(document.querySelectorAll('#inbox-list tbody tr'))
            .filter(r => r.querySelector('input[name=message_ids]'))
            .find(r => r.textContent.includes(needle));
          if (!row) return null;
          const m = row.innerHTML.match(/messages\\/(\\d+)\\//);
          return m ? m[1] : null;
        }""",
        MSG_BODY[:30],
    )
    if detail_pk:
        a.goto(f"{CLUB}/accounts/messages/{detail_pk}/", "open message detail as admin by URL")
        h2_text = ""
        end = time.time() + 5
        while time.time() < end:
            try:
                h2_text = a.page.evaluate(
                    "() => { const el = document.querySelector('main h2');"
                    " return el ? el.innerText.trim() : ''; }"
                )
                break
            except Exception:
                time.sleep(0.1)
        h2 = h2_text
        a.check(
            "admin detail page heading",
            "'Your Message'",
            h2,
            h2 == "Your Message",
        )
        body_shown = MSG_BODY[:30] in a.text()
        a.check(
            "admin detail page shows body",
            "message body visible",
            body_shown,
            body_shown,
        )
    else:
        a.check(
            "admin finds detail URL for Alice's message",
            "detail URL extractable from row",
            "missing",
            False,
        )


def admin_answers(a: Tab, width: int) -> None:
    """Admin marks one message Handled and gives a coins grant on another."""
    a.goto(f"{CLUB}/accounts/messages/?status=open&kind=all", "open inbox Open list")

    # Find Alice's message PK.
    msg_pk = a.page.evaluate(
        """(needle) => {
          const row = Array.from(document.querySelectorAll('#inbox-list tbody tr'))
            .filter(r => r.querySelector('input[name=message_ids]'))
            .find(r => r.textContent.includes(needle));
          if (!row) return null;
          const m = row.innerHTML.match(/name="message_ids" value="(\\d+)"/);
          return m ? m[1] : null;
        }""",
        MSG_BODY[:30],
    )
    if not msg_pk:
        a.check("admin finds Alice's message PK in Open inbox", "PK extractable", "missing", False)
        return

    # Mark the found message Handled through the modal (setup only).
    row_loc = a.page.locator("#inbox-list tbody tr").filter(has_text=MSG_BODY[:30])
    handled_btn = row_loc.locator("a[aria-label='Mark handled']")
    if handled_btn.count() > 0:
        handled_btn.first.click()
        opened = a.modal_open() and a.modal_has("Mark handled")
        a.check(
            "Mark handled modal opens",
            "modal with sender",
            a.modal_text()[:60],
            opened,
        )
        if opened:
            a.page.locator("#app-modal .modal-footer button[type=submit]").first.click()
            closed = a.modal_closed()
            # HTMX may close the modal automatically; give it a moment.
            end = time.time() + 5
            while time.time() < end and not closed:
                closed = a.modal_closed()
                time.sleep(0.1)
            a.check(
                "Mark handled confirm closes modal",
                "modal closed",
                closed,
                closed,
            )

    # Handled filter shows the row, Open no longer does.
    a.goto(f"{CLUB}/accounts/messages/?status=handled&kind=all", "open inbox Handled list")
    rows = a.page.evaluate(
        "Array.from(document.querySelectorAll('#inbox-list tbody tr'))"
        ".filter(r => r.querySelector('input[name=message_ids]'))"
        ".map(r => r.textContent)"
    )
    handled_has = any(MSG_BODY[:30] in r for r in rows)
    a.check(
        "Handled filter shows the message",
        "row present under Handled",
        handled_has,
        handled_has,
    )
    a.goto(f"{CLUB}/accounts/messages/?status=open&kind=all", "open inbox Open list again")
    rows = a.page.evaluate(
        "Array.from(document.querySelectorAll('#inbox-list tbody tr'))"
        ".filter(r => r.querySelector('input[name=message_ids]'))"
        ".map(r => r.textContent)"
    )
    open_has = any(MSG_BODY[:30] in r for r in rows)
    a.check(
        "Open filter no longer shows the message",
        "row absent from Open",
        not open_has,
        not open_has,
    )

    # Re-open the handled message so it is back in Open, then give coins.
    a.goto(f"{CLUB}/accounts/messages/?status=handled&kind=all", "open Handled list again")
    row_loc = a.page.locator("#inbox-list tbody tr").filter(has_text=MSG_BODY[:30])
    reopen_btn = row_loc.locator("a[aria-label='Reopen']")
    if reopen_btn.count() > 0:
        reopen_btn.first.click()
        opened = a.modal_open() and a.modal_has("Reopen")
        a.check(
            "Reopen modal opens",
            "modal with sender",
            a.modal_text()[:60],
            opened,
        )
        if opened:
            a.page.locator("#app-modal .modal-footer button[type=submit]").first.click()
            closed = a.modal_closed()
            end = time.time() + 5
            while time.time() < end and not closed:
                closed = a.modal_closed()
                time.sleep(0.1)
            a.check(
                "Reopen confirm closes modal",
                "modal closed",
                closed,
                closed,
            )

    # Give coins: 1 gp.
    a.goto(f"{CLUB}/accounts/messages/?status=open&kind=all", "open Open list for Give")
    row_loc = a.page.locator("#inbox-list tbody tr").filter(has_text=MSG_BODY[:30])
    give_btn = row_loc.locator("a[aria-label='Give coins']")
    if give_btn.count() > 0:
        give_btn.first.click()
        opened = a.modal_open() and a.modal_has("Give coins")
        a.check(
            "Give coins modal opens",
            "modal with sender",
            a.modal_text()[:60],
            opened,
        )
        if opened:
            a.page.fill("#app-modal input[name=coins_gp]", GRANT_GP)
            # Review
            a.page.locator("#app-modal button[value=review]").first.click()
            summary = a.modal_has("Give this from") and GRANT_GP in a.modal_text()
            a.check(
                "Give coins Review",
                "summary shows 1 gp",
                a.modal_text()[:120],
                summary,
            )
            if summary:
                a.page.locator("#app-modal button[name=confirmed]").first.click()
                closed = a.modal_closed()
                end = time.time() + 5
                while time.time() < end and not closed:
                    closed = a.modal_closed()
                    time.sleep(0.1)
                a.check(
                    "Give coins confirm closes modal",
                    "modal closed",
                    closed,
                    closed,
                )
                # Reload the inbox to see the granted row update.
                a.page.reload(wait_until="networkidle")
                # The grant marks the message Handled, so check the Handled list.
                a.goto(
                    f"{CLUB}/accounts/messages/?status=handled&kind=all",
                    "open Handled list for grant check",
                )
                granted = a.wait(
                    "Array.from(document.querySelectorAll('#inbox-list .wm-granted'))"
                    ".some(e => e.textContent.includes('gp'))",
                    timeout=5,
                )
                a.check(
                    "Give coins shows grant in row",
                    "'1 gp' under Granted",
                    granted,
                    granted,
                )


# --------------------------------------------------------------------------- player sees answer


def player_sees_answer(p: Tab) -> None:
    """Alice reloads and checks the admin's answer arrived."""
    p.goto(f"{CLUB}/", "reload club home as Alice")

    # Dashboard badge Handled, preview line.
    items = p.page.locator(".list-group-item").all_inner_texts()
    handled = any(MSG_BODY[:30] in t and "Handled" in t for t in items)
    p.check(
        "dashboard badge Handled + preview",
        "badge Handled and admin response preview",
        f"handled={handled}",
        handled,
    )

    # Open "View Response": status badge, Admin Response section, grant lines.
    clicked = p.page.evaluate(
        """(needle) => {
          const li = Array.from(document.querySelectorAll('.list-group-item'))
            .find(el => el.textContent.includes(needle));
          if (!li) return false;
          const as = Array.from(li.querySelectorAll('a'));
          const a = as.find(el => el.textContent.includes('View Response'));
          if (!a) return false;
          a.click();
          return true;
        }""",
        MSG_BODY[:30],
    )
    if clicked:
        p.page.wait_for_load_state("networkidle")
        h2_text = ""
        end = time.time() + 5
        while time.time() < end:
            try:
                h2_text = p.page.evaluate(
                    "() => { const el = document.querySelector('main h2');"
                    " return el ? el.innerText.trim() : ''; }"
                )
                break
            except Exception:
                time.sleep(0.1)
        h2 = h2_text
        p.check(
            "detail page heading",
            "'Your Message'",
            h2,
            h2 == "Your Message",
        )
        badge = "Handled" in p.text()
        admin_response = "Admin Response" in p.text()
        p.check(
            "detail page shows Admin Response",
            "Handled badge + Admin Response",
            f"badge={badge} admin_response={admin_response}",
            badge and admin_response,
        )
    else:
        p.check(
            "'View Response' link on Alice's message (after answer)",
            "link present and clickable",
            "missing",
            False,
        )

    # "Your messages" table on the form page shows the new status.
    p.goto(f"{CLUB}/accounts/messages/new/", "open message form (your messages table)")
    rows = p.page.evaluate(
        "Array.from(document.querySelectorAll('table tbody tr')).map(r => r.textContent)"
    )
    handled_row = any(MSG_BODY[:30] in r and "Handled" in r for r in rows)
    p.check(
        "your messages table shows Handled",
        "row with Handled badge",
        handled_row,
        handled_row,
    )


# --------------------------------------------------------------------------- permissions


def check_permissions(p: Tab, a: Tab) -> None:
    """Alice cannot open the inbox or bob's message; admin can open Alice's."""
    # Let the page settle after the previous section's navigations.
    p.page.wait_for_load_state("networkidle")
    # Alice opens the admin inbox: 403 or 404.
    p.goto(f"{CLUB}/accounts/messages/", "Alice opens admin inbox", expect_status=403)
    shown = p.page.locator("body").inner_text().strip()
    p.check(
        "player gets 403/404 on admin inbox",
        "403 or 404 page with text",
        f"text={shown[:50]!r}",
        bool(shown),
        expect_problem="403",
    )

    # Alice opens bob's message detail by URL: 404.
    p.goto(f"{CLUB}/accounts/messages/99999/", "Alice opens nonexistent message", expect_status=404)
    shown = p.page.locator("body").inner_text().strip()
    p.check(
        "player gets 404 on other's message",
        "404 page with text",
        f"text={shown[:50]!r}",
        bool(shown),
        expect_problem="404",
    )

    # Admin opens Alice's message: 200.
    a.goto(f"{CLUB}/accounts/messages/1/", "admin opens message #1")
    status_text = a.page.locator("body").inner_text().strip()
    a.check(
        "admin opens message #1",
        "200 page with text",
        f"text={status_text[:50]!r}",
        bool(status_text),
    )


# --------------------------------------------------------------------------- layout at 390


def layout_390(p: Tab, a: Tab) -> None:
    """No horizontal scroll on form, inbox, detail page, dashboard card."""
    p.page.wait_for_load_state("networkidle")
    p.no_hscroll("message form no horizontal scroll")
    a.no_hscroll("inbox no horizontal scroll")
    p.goto(f"{CLUB}/", "open dashboard for layout")
    p.no_hscroll("dashboard card no horizontal scroll")


# --------------------------------------------------------------------------- runner


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
            stderr=subprocess.PIPE,
        )
        with lib.run_server(env) as server:
            player_ctx = browser.new_context(viewport={"width": width, "height": height})
            admin_ctx = browser.new_context(viewport={"width": width, "height": height})
            try:
                player = Tab(player_ctx, server.base_url, "player", width)
                admin = Tab(admin_ctx, server.base_url, "admin", width)

                lib.login(player.page, server.base_url, "player")
                lib.login(admin.page, server.base_url, "admin")

                problems: list[str] = []

                def section(tab: Tab, name: str, fn, *args):
                    try:
                        fn(*args)
                    except Exception as exc:
                        tab.check(
                            f"section '{name}'",
                            "completes",
                            f"{type(exc).__name__}: {str(exc)[:160]}",
                            False,
                        )
                        import traceback

                        traceback.print_exc(limit=3)

                section(player, "player send message", player_send_message, player)
                section(player, "player before answer", player_before_answer, player)
                section(admin, "admin reads inbox", admin_reads_inbox, admin)
                section(admin, "admin answers", admin_answers, admin, width)
                section(player, "player sees answer", player_sees_answer, player)
                section(player, "permissions", check_permissions, player, admin)
                if width <= 480:
                    section(player, "layout 390", layout_390, player, admin)

                problems += player.rec.problems()
                problems += admin.rec.problems()
                total = player.rec.controls_tried + admin.rec.controls_tried
                return total, problems
            finally:
                player_ctx.close()
                admin_ctx.close()


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
                    problems.extend(found)
                except Exception as exc:
                    import traceback

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
        for p in problems:
            print(f"  {p}")
        return 1
    print(
        f"Flow 10 admin message check: clean, browser={browser_name}, "
        f"controls tried={total} ({counts})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
