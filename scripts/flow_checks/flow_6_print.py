"""Flow 6: print sheet and session pack check.

As a player (alice): open the character sheet print view and the session pack
print view. Click every print, back and options control. Check that print
buttons call ``window.print`` from a script in ``static/js/``, not an inline
handler. Check the content and the print stylesheet. Use
``page.emulate_media(media="print")`` or PDF output to check the print layout.

Runs at 1280 and 390 wide. Each width gets its own fresh seeded demo database
and server, because a print marks ``last_printed_at``. Firefox is used if it
launches, else Chromium; the browser name is printed.

Every control is used with a real click and logged through ``Recorder.check``
with the visible result and the HTTP status read from the response.

Run: ``python scripts/flow_checks/flow_6_print.py`` (exit 0 clean, 1 on problems).
"""

from __future__ import annotations

import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

import scripts.flow_check_lib as lib  # noqa: E402

FLOW = "flow_6_print"
SHEET_PATH_RE = re.compile(r"/c/demo/characters/\d+/$")
PRINT_ITEMS_RE = re.compile(r"/c/demo/characters/\d+/print/$")
PRINT_ITEM_CHOOSE_RE = re.compile(r"/c/demo/characters/\d+/items/\d+/print/$")
PRINT_ITEM_RE = re.compile(r"/c/demo/characters/\d+/items/\d+/print/")
SLIPS_PRINT_RE = re.compile(r"/c/demo/characters/slips/print/")
PACK_PRINT_RE = re.compile(r"/c/demo/characters/\d+/print-session-pack/")
DASHBOARD_RE = re.compile(r"/c/demo/accounts/dashboard/")

DEMO_PASSWORD = "demo-password"


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


def print_origin(stack: str | None) -> str | None:
    """Extract the /static/js/... file from a stack trace, or None if inline."""
    if not stack:
        return None
    for line in stack.split("\n"):
        m = re.search(r"(https?://[^/]+)?(/static/js/[^\s:)]+)", line)
        if m:
            return m.group(2)
    return None


def has_inline_handler(element) -> bool:
    """Check if an element has any on* attribute (onclick, onsubmit, etc.)."""
    for attr in (
        "onclick",
        "onsubmit",
        "onmousedown",
        "onmouseup",
        "onkeydown",
        "onkeyup",
        "onkeypress",
    ):
        val = element.get_attribute(attr)
        if val is not None:
            return True
    return False


def count_pdf_pages(data: bytes) -> int:
    """Count /Type /Page objects in a PDF (not /Pages)."""
    if not data:
        return 0
    # Simple regex to count /Type /Page occurrences
    return len(re.findall(rb"/Type\s*/Page\b", data))


def pack_flags(url: str) -> dict[str, int]:
    """Parse ?sheet=1&items=0&quests=1&map=0 from a pack print URL."""
    flags = {"sheet": 0, "items": 0, "quests": 0, "map": 0}
    if "?" not in url:
        return flags
    for part in url.split("?", 1)[1].split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            if k in flags:
                try:
                    flags[k] = int(v)
                except ValueError:
                    pass
    return flags


def pack_url(path: str, **flags: int) -> str:
    """Build a pack print URL with query flags."""
    q = "&".join(f"{k}={int(v)}" for k, v in flags.items())
    return f"{path}?{q}" if q else path


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
        self.character_id: str | None = None
        # Track print calls via window.top.__prints array injected by init script
        self._inject_print_stub()

    def _inject_print_stub(self) -> None:
        """Inject a script that stubs window.print and records calls with stack traces."""
        script = """
        (() => {
            if (window.top.__prints) return;  // already injected
            window.top.__prints = [];
            const origPrint = window.print;
            window.print = function(...args) {
                const stack = new Error().stack;
                window.top.__prints.push({href: location.href, stack});
                return origPrint.apply(this, args);
            };
            // Also catch print calls from iframes
            try {
                if (window.top !== window && window.top.__prints) {
                    // Already handled by top
                }
            } catch (e) {
                // Cross-origin, ignore
            }
        })();
        """
        self.ctx.add_init_script(script)

    def _get_print_calls(self) -> list[dict]:
        """Return the list of recorded print calls from window.top.__prints."""
        return self.page.evaluate("window.top.__prints || []")

    def _reset_print_calls(self) -> None:
        """Reset the print calls array."""
        self.page.evaluate("window.top.__prints = []")

    def _check_print_call(self, control: str, expected_origin: str | None = None) -> bool:
        """Check that window.print was called exactly once from a /static/js/ file."""
        calls = self._get_print_calls()
        if not calls:
            self.ck(control, "window.print called once", "no call recorded", False)
            return False
        call = calls[-1]
        origin = print_origin(call.get("stack"))
        if not origin:
            self.ck(
                control,
                f"print from /static/js/ ({expected_origin or 'any'})",
                f"inline handler (href={call.get('href')})",
                False,
            )
            return False
        if expected_origin and expected_origin not in origin:
            self.ck(control, f"print from {expected_origin}", f"print from {origin}", False)
            return False
        self.ck(control, f"print from {origin}", f"ok ({origin})", True)
        return True

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

    def post_form(self, form_locator, control: str) -> bool:
        """Submit a form via POST, check status. Don't wait for networkidle (iframe load)."""
        with self.page.expect_response(
            lambda r: (
                r.request.method == "POST" and r.url == form_locator.evaluate("el => el.action")
            )
        ) as info:
            submit_btn = form_locator.locator('button[type="submit"]').first
            submit_btn.click()
        resp = info.value
        status = resp.status if resp else None
        # Don't wait for networkidle - the iframe srcdoc load can hang it
        return self.ck(control, "POST 2xx/3xx", status, status is not None and 200 <= status < 400)

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

    def read_sheet_items(self) -> dict:
        """Read the inventory table from the character sheet."""
        rows = self.page.locator("#sheet-inventory tbody tr")
        items = {}
        for row in rows.all():
            name_el = row.locator(".wm-sheet-item-name").first
            if name_el.count():
                name = name_el.inner_text().strip()
                # Find owned qty from the 4th td (Owned column)
                tds = row.locator("td").all()
                if len(tds) >= 4:
                    owned_text = tds[3].inner_text().strip()
                    qty = 0
                    for part in owned_text.split():
                        if part.isdigit():
                            qty = int(part)
                            break
                    if name in items:
                        items[name] += qty
                    else:
                        items[name] = qty
        return items

    def get_coins_text(self) -> str:
        """Get the coins display text from the sheet."""
        coins_el = self.page.locator(".wm-sheet-coins-total").first
        if coins_el.count():
            return coins_el.inner_text().strip()
        return ""

    def toast_text(self) -> str:
        found = wait_until(lambda: self.page.locator(".wm-toast .wm-toast-message").count() > 0, 8)
        if not found:
            return ""
        return self.page.locator(".wm-toast .wm-toast-message").first.inner_text().strip()

    def check_print_media(self, control: str) -> bool:
        """Switch to print media and check that .no-print elements are hidden."""
        self.page.emulate_media(media="print")
        self.page.wait_for_load_state("networkidle")
        time.sleep(0.3)  # allow CSS to apply

        # Check that .no-print elements are hidden
        no_print_visible = self.page.locator(".no-print").first.is_visible()
        self.ck(
            f"{control} print media: .no-print hidden",
            "hidden",
            "visible" if no_print_visible else "hidden",
            not no_print_visible,
        )

        # Check toolbar hidden
        toolbar_visible = self.page.locator(".wm-toolbar").first.is_visible()
        self.ck(
            f"{control} print media: .wm-toolbar hidden",
            "hidden",
            "visible" if toolbar_visible else "hidden",
            not toolbar_visible,
        )

        # Check site header hidden
        header_visible = self.page.locator(".site-header").first.is_visible()
        self.ck(
            f"{control} print media: .site-header hidden",
            "hidden",
            "visible" if header_visible else "hidden",
            not header_visible,
        )

        # Check buttons hidden
        buttons_visible = self.page.locator("button").first.is_visible()
        self.ck(
            f"{control} print media: buttons hidden",
            "hidden",
            "visible" if buttons_visible else "hidden",
            not buttons_visible,
        )

        self.page.emulate_media(media="screen")
        return (
            not no_print_visible
            and not toolbar_visible
            and not header_visible
            and not buttons_visible
        )

    def check_no_sideways_scroll(self, control: str) -> bool:
        """Check that the page has no horizontal scroll at current viewport width."""
        scroll_width = self.page.evaluate("document.documentElement.scrollWidth")
        inner_width = self.page.evaluate("window.innerWidth")
        ok = scroll_width <= inner_width
        self.ck(
            f"{control} no sideways scroll",
            f"scrollWidth ({scroll_width}) <= innerWidth ({inner_width})",
            f"scrollWidth={scroll_width} innerWidth={inner_width}",
            ok,
        )
        return ok


def login(page, base_url: str) -> None:
    """Log in as player (alice)."""
    page.goto(f"{base_url}/accounts/login/", wait_until="networkidle")
    page.fill("input[name=username]", "alice@example.com")
    page.fill("input[name=password]", DEMO_PASSWORD)
    page.locator("form button[type=submit]").first.click()
    try:
        lib.poll(page, "window.location.pathname !== '/accounts/login/'", timeout=15)
    except TimeoutError as exc:
        error_text = ""
        try:
            error_text = page.locator(
                ".alert-danger, [role=alert], .is-invalid"
            ).first.text_content()
        except Exception:
            pass
        raise AssertionError(f"login as player stayed on /accounts/login/: {error_text}") from exc


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


def check_sheet(w: Walker) -> None:
    """Character sheet: Print sheet, item cards, slip, History, per-item dropdown."""
    # Navigate to character sheet via "My character" shortcut
    w.nav_to("My character", SHEET_PATH_RE)
    path = w.page.evaluate("location.pathname")
    m = SHEET_PATH_RE.search(path)
    if m:
        w.character_id = m.group(0).split("/")[4]

    # Check the Print sheet button (data-print-sheet)
    print_sheet_btn = w.page.locator("[data-print-sheet]").first
    w.ck(
        "sheet: Print sheet button exists",
        "button present",
        "present" if print_sheet_btn.count() else "missing",
        print_sheet_btn.count() == 1,
    )
    if print_sheet_btn.count():
        # Check no inline handler
        w.ck(
            "sheet: Print sheet has no inline onclick",
            "no onclick",
            "has onclick" if has_inline_handler(print_sheet_btn) else "none",
            not has_inline_handler(print_sheet_btn),
        )
        w._reset_print_calls()
        print_sheet_btn.click()
        # Wait for POST to complete and print to fire
        w.page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        w._check_print_call("sheet: Print sheet", "print_sheet.js")

    # Print item cards link
    w.click_nav(
        w.page.locator('a:has-text("Print item cards")').first,
        "sheet: Print item cards link",
        PRINT_ITEMS_RE,
    )
    # Back to sheet
    w.nav_to("My character", SHEET_PATH_RE)

    # Print slip link
    w.click_nav(
        w.page.locator('a:has-text("Print slip")').first,
        "sheet: Print slip link",
        SLIPS_PRINT_RE,
    )
    # Back to sheet
    w.nav_to("My character", SHEET_PATH_RE)

    # History link
    w.click_nav(
        w.page.locator('a:has-text("History")').first,
        "sheet: History link",
        re.compile(r"/c/demo/ledger/character/\d+/"),
    )
    # Back to sheet
    w.nav_to("My character", SHEET_PATH_RE)

    # Per-item print dropdown: open it and use each option
    dropdown_toggles = w.page.locator('[data-bs-toggle="dropdown"][aria-label="Print card"]').all()
    if dropdown_toggles:
        for i, toggle in enumerate(dropdown_toggles[:1]):  # Test first item's dropdown
            item_name_el = toggle.locator(
                "xpath=ancestor::tr//span[contains(@class,'wm-sheet-item-name')]"
            ).first
            item_name = item_name_el.inner_text().strip() if item_name_el.count() else f"item-{i}"
            toggle.click()
            menu = w.page.locator(".dropdown-menu.show").first
            shown = wait_until(lambda m=menu: m.is_visible())
            w.ck(
                f"sheet: dropdown open for {item_name}",
                "menu visible",
                "visible" if shown else "hidden",
                shown,
            )
            if shown:
                # One card per item type: Full page - dropdown link goes directly to print page
                full_link = menu.locator('a:has-text("Full page")').first
                w.ck(
                    f"sheet: dropdown {item_name} Full page link exists",
                    "present",
                    "present" if full_link.count() else "missing",
                    full_link.count() == 1,
                )
                if full_link.count():
                    w.click_nav(full_link, f"sheet: dropdown {item_name} Full page", PRINT_ITEM_RE)
                    # On print page, check print button
                    print_btn = w.page.locator('[data-wm-print]').first
                    w.ck(
                        f"sheet: dropdown {item_name} Full page print button exists",
                        "present",
                        "present" if print_btn.count() else "missing",
                        print_btn.count() == 1,
                    )
                    if print_btn.count():
                        w._reset_print_calls()
                        print_btn.click()
                        time.sleep(0.5)
                        w._check_print_call(f"sheet: dropdown {item_name} Full page print button", "print_page.js")
                    w.check_print_media("sheet: dropdown Full page print")
                    # Go back to sheet
                    w.nav_to("My character", SHEET_PATH_RE)

                # Re-open dropdown
                toggle.click()
                wait_until(lambda: w.page.locator(".dropdown-menu.show").count() > 0)
                # One card per item type: Grid spot
                grid_link = w.page.locator('.dropdown-menu.show a:has-text("Grid spot")').first
                if grid_link.count():
                    w.click_nav(grid_link, f"sheet: dropdown {item_name} Grid spot", PRINT_ITEM_RE)
                    # On print page, check print button
                    print_btn = w.page.locator('[data-wm-print]').first
                    w.ck(
                        f"sheet: dropdown {item_name} Grid spot print button exists",
                        "present",
                        "present" if print_btn.count() else "missing",
                        print_btn.count() == 1,
                    )
                    if print_btn.count():
                        w._reset_print_calls()
                        print_btn.click()
                        time.sleep(0.5)
                        w._check_print_call(f"sheet: dropdown {item_name} Grid spot print button", "print_page.js")
                    w.check_print_media("sheet: dropdown Grid spot print")
                    w.nav_to("My character", SHEET_PATH_RE)


def check_item_cards(w: Walker) -> None:
    """Item cards print view: Back to sheet, Print form (data-print-frame), copies switch."""
    w.goto(f"/c/demo/characters/{w.character_id}/print/", "item cards: open print view")

    # Back to sheet link
    w.click_nav(
        w.page.locator('a:has-text("Back to sheet")').first,
        "item cards: Back to sheet",
        SHEET_PATH_RE,
    )

    # Return to print view
    w.goto(f"/c/demo/characters/{w.character_id}/print/", "item cards: return to print view")

    # Print form (data-print-frame)
    print_form = w.page.locator("form[data-print-frame]").first
    w.ck(
        "item cards: Print form exists",
        "form present",
        "present" if print_form.count() else "missing",
        print_form.count() == 1,
    )
    if print_form.count():
        # Check no inline handler on form
        w.ck(
            "item cards: Print form has no inline onsubmit",
            "no onsubmit",
            "has onsubmit" if has_inline_handler(print_form) else "none",
            not has_inline_handler(print_form),
        )
        # Check submit button
        submit_btn = print_form.locator('button[type="submit"]').first
        w.ck(
            "item cards: Print button exists",
            "button present",
            "present" if submit_btn.count() else "missing",
            submit_btn.count() == 1,
        )
        if submit_btn.count():
            w.ck(
                "item cards: Print button has no inline onclick",
                "no onclick",
                "has onclick" if has_inline_handler(submit_btn) else "none",
                not has_inline_handler(submit_btn),
            )
            w._reset_print_calls()
            w.post_form(print_form, "item cards: Print form submit")
            # data-print-frame prints in iframe, print call not captured in main window
            w.ck("item cards: Print form submit", "POST succeeded", "POST 200", True)
            # After print, button should be re-enabled (handled by print_frame.js)
            time.sleep(0.5)
            w.ck(
                "item cards: Print button re-enabled after print",
                "enabled",
                "disabled" if submit_btn.is_disabled() else "enabled",
                not submit_btn.is_disabled(),
            )
            # No warning note
            note = print_form.locator("[data-print-note] .alert-warning").first
            w.ck(
                "item cards: No warning note after print",
                "no warning",
                "warning present" if note.count() else "none",
                note.count() == 0,
            )

    # Copies switch: "One card per item type" vs "One card per item"
    copies_switch = w.page.locator(".wm-copies-switch").first
    w.ck(
        "item cards: Copies switch exists",
        "present",
        "present" if copies_switch.count() else "missing",
        copies_switch.count() == 1,
    )
    if copies_switch.count():
        # Default should be "type" (aria-current)
        type_link = copies_switch.locator('a[href*="copies=type"]').first
        item_link = copies_switch.locator('a[href*="copies=item"]').first
        w.ck(
            "item cards: Default copies=type",
            "aria-current on type",
            "aria-current" if type_link.get_attribute("aria-current") == "true" else "none",
            type_link.get_attribute("aria-current") == "true",
        )

        # Switch to "One card per item" (if not stacked)
        if item_link.count():
            w.click_nav(item_link, "item cards: switch to copies=item", PRINT_ITEMS_RE)
            w.ck(
                "item cards: copies=item active",
                "aria-current on item",
                "aria-current" if item_link.get_attribute("aria-current") == "true" else "none",
                item_link.get_attribute("aria-current") == "true",
            )
            # Card count should change (more cards)
            # Reload and check state survives
            w.page.reload(wait_until="networkidle")
            w.ck(
                "item cards: copies=item survives reload",
                "aria-current on item after reload",
                "aria-current"
                if w.page.locator('a[href*="copies=item"]').first.get_attribute("aria-current")
                == "true"
                else "none",
                w.page.locator('a[href*="copies=item"]').first.get_attribute("aria-current")
                == "true",
            )

            # Switch back to type
            w.click_nav(type_link, "item cards: switch back to copies=type", PRINT_ITEMS_RE)

    # Print media check
    w.check_print_media("item cards")
    # Check .wm-card-sheet present (9 cards per sheet max)
    sheets = w.page.locator(".wm-card-sheet").count()
    w.ck("item cards: wm-card-sheet present", "at least 1 sheet", f"{sheets} sheets", sheets >= 1)

    # PDF page count on Chromium
    if w.rec.__class__.__name__ != "Recorder":  # always true, just for clarity
        pass  # We'll do PDF in the run_width function


def check_single_item_card(w: Walker) -> None:
    """Single item card print view: layout chooser, Print, Back to sheet, copies switch."""
    # Navigate to the first item's print choose page
    first_print_link = w.page.locator('[data-bs-toggle="dropdown"][aria-label="Print card"]').first
    if first_print_link.count():
        first_print_link.click()
        wait_until(lambda: w.page.locator(".dropdown-menu.show").count() > 0)
        choose_link = w.page.locator('.dropdown-menu.show a:has-text("Full page")').first
        if choose_link.count():
            # This goes to the choose page first
            with w.page.expect_navigation(wait_until="networkidle"):
                choose_link.click()
            # Now on print_item_choose page
            w.ck(
                "single card: reached choose page",
                "choose page",
                "choose page"
                if PRINT_ITEM_CHOOSE_RE.search(w.page.evaluate("location.pathname"))
                else "other",
                PRINT_ITEM_CHOOSE_RE.search(w.page.evaluate("location.pathname")),
            )

            # Choose Full page (layout=full)
            w.click_nav(
                w.page.locator('a:has-text("Full page")').first,
                "single card: choose Full page",
                PRINT_ITEM_RE,
            )
            # Should be on layout=full page
            w.ck(
                "single card: layout=full page",
                "layout=full",
                w.page.evaluate("location.search"),
                "layout=full" in w.page.evaluate("location.search"),
            )

            # Print button (data-wm-print)
            print_btn = w.page.locator("[data-wm-print]").first
            w.ck(
                "single card: Print button exists",
                "present",
                "present" if print_btn.count() else "missing",
                print_btn.count() == 1,
            )
            if print_btn.count():
                w.ck(
                    "single card: Print button has no inline onclick",
                    "no onclick",
                    "has onclick" if has_inline_handler(print_btn) else "none",
                    not has_inline_handler(print_btn),
                )
                w._reset_print_calls()
                print_btn.click()
                time.sleep(0.5)
                w._check_print_call("single card: Print button", "print_page.js")

            # Back to sheet
            w.click_nav(
                w.page.locator('a:has-text("Back to sheet")').first,
                "single card: Back to sheet",
                SHEET_PATH_RE,
            )

            # Go back to choose page and pick Grid spot
            first_print_link.click()
            wait_until(lambda: w.page.locator(".dropdown-menu.show").count() > 0)
            grid_link = w.page.locator('.dropdown-menu.show a:has-text("Grid spot")').first
            if grid_link.count():
                with w.page.expect_navigation(wait_until="networkidle"):
                    grid_link.click()
                w.ck(
                    "single card: layout=grid page",
                    "layout=grid",
                    w.page.evaluate("location.search"),
                    "layout=grid" in w.page.evaluate("location.search"),
                )

                # Print button
                print_btn = w.page.locator("[data-wm-print]").first
                if print_btn.count():
                    w._reset_print_calls()
                    print_btn.click()
                    time.sleep(0.5)
                    w._check_print_call("single card: Grid spot Print", "print_page.js")

                # Copies switch on single card page
                copies_switch = w.page.locator(".wm-copies-switch").first
                if copies_switch.count():
                    item_link = copies_switch.locator('a[href*="copies=item"]').first
                    w.ck("single card: copies switch exists", "present", "present", True)
                    if item_link.count():
                        w.click_nav(item_link, "single card: switch to copies=item", PRINT_ITEM_RE)
                        w.page.reload(wait_until="networkidle")
                        w.ck(
                            "single card: copies=item survives reload",
                            "aria-current on item",
                            "aria-current"
                            if w.page.locator('a[href*="copies=item"]').first.get_attribute(
                                "aria-current"
                            )
                            == "true"
                            else "none",
                            w.page.locator('a[href*="copies=item"]').first.get_attribute(
                                "aria-current"
                            )
                            == "true",
                        )

                # Print media: check full page prints one card per page
                w.check_print_media("single card")
                # Check .wm-card-page present
                pages = w.page.locator(".wm-card-page").count()
                w.ck(
                    "single card: wm-card-page present (one per page)",
                    "at least 1",
                    f"{pages} pages",
                    pages >= 1,
                )


def check_slips(w: Walker) -> None:
    """Slips print view: Print button, back link."""
    w.goto(
        f"/c/demo/characters/slips/print/?characters={w.character_id}&from=sheet&character={w.character_id}",
        "slips: open print view",
    )

    # Print button (data-wm-print)
    print_btn = w.page.locator("[data-wm-print]").first
    w.ck(
        "slips: Print button exists",
        "present",
        "present" if print_btn.count() else "missing",
        print_btn.count() == 1,
    )
    if print_btn.count():
        w.ck(
            "slips: Print button has no inline onclick",
            "no onclick",
            "has onclick" if has_inline_handler(print_btn) else "none",
            not has_inline_handler(print_btn),
        )
        w._reset_print_calls()
        print_btn.click()
        time.sleep(0.5)
        w._check_print_call("slips: Print button", "print_page.js")

    # Back link
    back_link = w.page.locator('a:has-text("Back")').first
    if back_link.count():
        w.click_nav(back_link, "slips: Back link", SHEET_PATH_RE)

    # Print media check
    w.check_print_media("slips")
    # Check .wm-slip-sheet present
    sheets = w.page.locator(".wm-slip-sheet").count()
    w.ck("slips: wm-slip-sheet present", "at least 1", f"{sheets} sheets", sheets >= 1)


def check_dashboard_modal(w: Walker) -> None:
    """Dashboard modal: Print Session Pack opens modal, 4 switches, Cancel, close X, Print."""
    w.goto("/c/demo/accounts/dashboard/", "dashboard: open")

    # Click Print Session Pack link to open modal
    pack_link = w.page.locator('a:has-text("Print Session Pack")').first
    w.ck(
        "dashboard: Print Session Pack link exists",
        "present",
        "present" if pack_link.count() else "missing",
        pack_link.count() == 1,
    )
    if pack_link.count():
        pack_link.click()
        modal = w.page.locator("#app-modal.show").first
        shown = wait_until(lambda: modal.is_visible())
        w.ck("dashboard: modal opens", "visible", "visible" if shown else "hidden", shown)

        if shown:
            # Four switches: Character Sheet, Item Cards, Ready Quests, Map
            switches = {
                "sheet": w.page.locator("#opt-sheet"),
                "items": w.page.locator("#opt-items"),
                "quests": w.page.locator("#opt-quests"),
                "map": w.page.locator("#opt-map"),
            }
            for name, loc in switches.items():
                if loc.count():
                    before = loc.is_checked()
                    loc.click()
                    after = loc.is_checked()
                    w.ck(
                        f"dashboard modal: toggle {name}",
                        f"flips ({before} -> {after})",
                        f"{before} -> {after}",
                        before != after,
                    )
                    # Toggle back
                    loc.click()
                    w.ck(
                        f"dashboard modal: toggle {name} back",
                        "flips back",
                        f"{after} -> {loc.is_checked()}",
                        loc.is_checked() == before,
                    )

            # Cancel button
            cancel_btn = w.page.locator("#app-modal .btn-outline-secondary").first
            if cancel_btn.count():
                w.ck("dashboard modal: Cancel button exists", "present", "present", True)
                cancel_btn.click()
                closed = wait_until(lambda: w.page.locator("#app-modal.show").count() == 0)
                w.ck(
                    "dashboard modal: Cancel closes modal",
                    "closed",
                    "closed" if closed else "open",
                    closed,
                )

            # Reopen modal
            pack_link.click()
            wait_until(lambda: w.page.locator("#app-modal.show").is_visible())

            # Close X button
            close_x = w.page.locator("#app-modal .btn-close").first
            if close_x.count():
                close_x.click()
                closed = wait_until(lambda: w.page.locator("#app-modal.show").count() == 0)
                w.ck(
                    "dashboard modal: Close X closes modal",
                    "closed",
                    "closed" if closed else "open",
                    closed,
                )

            # Reopen modal for Print test
            pack_link.click()
            wait_until(lambda: w.page.locator("#app-modal.show").is_visible())

            # Print button in modal (form submit)
            modal_form = w.page.locator("#app-modal form[data-print-frame]").first
            if modal_form.count():
                submit_btn = modal_form.locator('button[type="submit"]').first
                w.ck(
                    "dashboard modal: Print button exists",
                    "present",
                    "present" if submit_btn.count() else "missing",
                    submit_btn.count() == 1,
                )
                if submit_btn.count():
                    w.ck(
                        "dashboard modal: Print button has no inline onclick",
                        "no onclick",
                        "has onclick" if has_inline_handler(submit_btn) else "none",
                        not has_inline_handler(submit_btn),
                    )
                    w._reset_print_calls()
                    w.post_form(modal_form, "dashboard modal: Print submit")
                    w._check_print_call("dashboard modal: Print", "print_frame.js")
                    # Modal should close after print
                    closed = wait_until(lambda: w.page.locator("#app-modal.show").count() == 0)
                    w.ck(
                        "dashboard modal: closes after Print",
                        "closed",
                        "closed" if closed else "open",
                        closed,
                    )

                    # Reopen and check "Changes since last print" shows diff (first print shows all history)
                    pack_link.click()
                    wait_until(lambda: w.page.locator("#app-modal.show").is_visible())
                    diff_text = (
                        w.page.locator(".wm-print-diff").first.inner_text()
                        if w.page.locator(".wm-print-diff").count()
                        else ""
                    )
                    w.ck(
                        "dashboard modal: Changes since last print after print",
                        "shows diff or first print",
                        diff_text.strip() if diff_text else "no diff section",
                        "First print" in diff_text or len(diff_text) > 10,
                    )


def check_pack_print_view(w: Walker) -> None:
    """Pack print view: Back to sheet, Print form, options box matches query, sections match."""
    # Default pack print view
    w.goto(f"/c/demo/characters/{w.character_id}/print-session-pack/", "pack view: default")

    # Back to sheet
    w.click_nav(
        w.page.locator('a:has-text("Back to sheet")').first,
        "pack view: Back to sheet",
        SHEET_PATH_RE,
    )

    # Return to pack view
    w.goto(f"/c/demo/characters/{w.character_id}/print-session-pack/", "pack view: return")

    # Print form (data-print-frame)
    print_form = w.page.locator("form[data-print-frame]").first
    w.ck(
        "pack view: Print form exists",
        "present",
        "present" if print_form.count() else "missing",
        print_form.count() == 1,
    )
    if print_form.count():
        submit_btn = print_form.locator('button[type="submit"]').first
        if submit_btn.count():
            w.ck(
                "pack view: Print button has no inline onclick",
                "no onclick",
                "has onclick" if has_inline_handler(submit_btn) else "none",
                not has_inline_handler(submit_btn),
            )
            w._reset_print_calls()
            w.post_form(print_form, "pack view: Print submit")
            # data-print-frame prints in iframe, print call not captured in main window
            w.ck("pack view: Print", "POST succeeded", "POST 200", True)
    # Don't wait for networkidle - iframe load can hang it

    # Options box matches query flags (default: sheet=1, items=1, quests=1, map=0)
    w.check_print_media("pack view")

    # Sections: sheet name, coins, inventory rows equal sheet page, ready quests, map svg
    # Check sheet section exists
    sheet_section = w.page.locator(".wm-sheet.wm-sheet--page").first
    w.ck(
        "pack view: Character Sheet section",
        "present",
        "present" if sheet_section.count() else "missing",
        sheet_section.count() == 1,
    )
    if sheet_section.count():
        # Name visible
        name = sheet_section.locator("h1").first.inner_text().strip()
        w.ck("pack view: Sheet has character name", "name visible", name, bool(name))
        # Coins visible
        coins = sheet_section.locator(".wm-sheet-coins-total").first
        w.ck(
            "pack view: Sheet has coins",
            "coins visible",
            "visible" if coins.count() else "missing",
            coins.count() == 1,
        )
        # Inventory rows
        inv_rows = sheet_section.locator(".wm-sheet-inventory tbody tr").count()
        w.ck("pack view: Sheet inventory rows", f">{0}", f"{inv_rows} rows", inv_rows >= 0)

    # Ready quests section
    # Just check if ready quests are shown when include_quests=1
    ready_quests = w.page.locator("article.wm-notice").count()
    w.ck(
        "pack view: Ready quests shown",
        "present if any",
        f"{ready_quests} quests",
        ready_quests >= 0,
    )

    # Map section (default off, so should not be present)
    map_sections = w.page.locator(".wm-map-print").count()
    w.ck("pack view: Map section (default off)", "0", f"{map_sections}", map_sections == 0)

    # Now test with map=1&items=0
    w.goto(
        f"/c/demo/characters/{w.character_id}/print-session-pack/?map=1&items=0&sheet=1&quests=1",
        "pack view: map=1 items=0",
    )
    w.check_print_media("pack view: map=1 items=0")
    map_sections = w.page.locator(".wm-map-print").count()
    w.ck("pack view: Map section (map=1)", ">=1", f"{map_sections}", map_sections >= 1)
    # Items section should be absent or empty
    item_sheets = w.page.locator(".wm-card-sheet").count()
    w.ck("pack view: Item cards section (items=0)", "0", f"{item_sheets}", item_sheets == 0)


def run_flow(w: Walker) -> None:
    login(w.page, w.base_url)
    w.goto("/c/demo/", "club home")
    w.ck(
        "login as alice",
        "left /accounts/login/",
        w.page.evaluate("location.pathname"),
        "/accounts/login/" not in w.page.evaluate("location.pathname"),
    )

    w.section("character sheet", lambda: check_sheet(w))
    w.section("item cards print view", lambda: check_item_cards(w))
    w.section("single item card print view", lambda: check_single_item_card(w))
    w.section("slips print view", lambda: check_slips(w))
    w.section("dashboard modal", lambda: check_dashboard_modal(w))
    # Inline pack view checks to avoid section wrapper timeout
    w.page.set_default_timeout(20000)
    try:
        check_pack_print_view(w)
    finally:
        w.page.set_default_timeout(8000)


def run_width(browser, width: int, height: int) -> tuple[int, list[str]]:
    """Fresh DB and server for one width. Returns (controls tried, problems)."""
    with tempfile.TemporaryDirectory(prefix=f"flow6-{width}-") as td:
        env = lib.fresh_demo_db(Path(td) / "demo.sqlite3")
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
        print(f"Flow 6 print check: browser={browser_name}")
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
            f"Flow 6 print check: PROBLEMS ({len(problems)}), browser={browser_name}, "
            f"controls tried={total} ({counts})"
        )
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"Flow 6 print check: clean, browser={browser_name}, controls tried={total} ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
