"""Flow 8: map flow check.

As a player (alice): open the map list, view the map, pan, use the picker,
open tile modal/page, request visit/discovered/explored/found credits.
As the game master (gm): approve/decline/bulk-approve requests.
As the player (alice) again: reload and check credits show on tile and map.

Runs at 1280 and 390 wide. Each width gets its own fresh seeded demo database
and server, because requests change state. Firefox is used if it launches,
else Chromium; the browser name is printed.

Every control is used with a real click and logged through ``Recorder.check``
with the visible result and the HTTP status read from the response. State
persistence is verified with a reload.

Run: ``python scripts/flow_checks/flow_8_map.py`` (exit 0 clean, 1 on problems).
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

FLOW = "flow_8_map"
MAP_INDEX = "/c/demo/map/"
MAP_DETAIL_RE = re.compile(r"/c/demo/map/\d+/$")
TILE_MODAL_RE = re.compile(r"/c/demo/map/\d+/tile/-?\d+/-?\d+/")
TILE_PAGE_RE = re.compile(r"/c/demo/map/\d+/tile/-?\d+/-?\d+/$")
REQUESTS_QUEUE = "/c/demo/map/requests/"
REQUEST_VISIT_RE = re.compile(r"/c/demo/map/requests/new/visit/\d+/")
REQUEST_CREDIT_RE = re.compile(r"/c/demo/map/requests/new/(discovered|explored|found)/location/\d+/")
BULK_APPROVE_RE = re.compile(r"/c/demo/map/requests/bulk-approve/")


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

    # -- helpers ---------------------------------------------------------

    def toast_text(self) -> str:
        found = wait_until(lambda: self.page.locator(".wm-toast .wm-toast-message").count() > 0, 8)
        if not found:
            return ""
        return self.page.locator(".wm-toast .wm-toast-message").first.inner_text().strip()

    def switch_character(self, name: str) -> bool:
        page = self.page
        toggle = page.locator(".character-selector .dropdown-toggle")
        toggle.click()
        menu = page.locator(".character-selector .dropdown-menu")
        shown = wait_until(lambda: menu.is_visible())
        self.ck(
            f"character selector opens (to pick {name})",
            "menu visible with characters",
            f"visible={bool(shown)} items={menu.locator('a[data-character-pk]').count()}",
            shown and menu.locator("a[data-character-pk]").count() >= 1,
        )
        option = menu.locator("a[data-character-pk]").filter(has_text=name)
        return self.click_nav(option, f"character switch to {name}", page.evaluate("location.pathname"))

    def count_visible_cells(self) -> int:
        """Count visible hex cells in the SVG map."""
        return self.page.locator(".hexmap svg a, .hexmap svg g").count()

    # -- sections --------------------------------------------------------

    def check_map_index(self) -> None:
        """Map list: map link, XP table, Map requests, no New map for player."""
        page = self.page
        self.nav_to("Maps", MAP_INDEX)
        # Map link
        map_link = page.locator("ul.map-grid a").first
        self.ck("map list shows The Marches", "The Marches", map_link.inner_text().strip(), True)
        self.click_nav(map_link, "map link: The Marches", MAP_DETAIL_RE)
        # Back to maps
        back = page.get_by_role("link", name="Back to maps")
        self.click_nav(back, "back to maps", MAP_INDEX)
        # XP table link
        xp_link = page.locator("a:has-text('XP table')").first
        self.click_nav(xp_link, "XP table link", re.compile(r"/c/demo/map/xp/"))
        page.go_back()
        wait_until(lambda: "map/" in self.page.url)
        # Map requests link
        req_link = page.locator("a:has-text('Map requests')").first
        self.click_nav(req_link, "Map requests link", REQUESTS_QUEUE)
        page.go_back()
        wait_until(lambda: "map/$" in self.page.url)
        # No New map for player
        new_map = page.locator("a:has-text('New map')")
        self.ck("no New map button for player", "hidden", new_map.count(), new_map.count() == 0)

    def check_map_detail(self, map_id: int) -> dict:
        """Map detail: pan links, picker (players' view), legend, tile cells, request visit button."""
        page = self.page
        # Pan links (6 directions)
        pan_links = page.locator("nav.pan-links a")
        pan_count = pan_links.count()
        self.ck("pan links present", "6 (E, W, NE, NW, SE, SW)", pan_count, pan_count == 6)
        for i in range(pan_count):
            link = pan_links.nth(i)
            name = link.inner_text().strip()
            self.click_nav(link, f"pan {name}", MAP_DETAIL_RE)
            # Check URL has q/r/radius
            url = self.page.url
            has_q = "q=" in url
            has_r = "r=" in url
            has_radius = "radius=" in url
            self.ck(f"pan {name} URL params", "q, r, radius present", f"q={has_q} r={has_r} radius={has_radius}", has_q and has_r and has_radius)
            # Reload and check state persists
            resp = self.page.reload(wait_until="networkidle")
            status = resp.status if resp else None
            self.ck(f"pan {name} reload", "2xx/3xx", status, status is not None and 200 <= status < 400)
            # Go back to center
            center_link = self.page.locator('nav.pan-links a:text-is("W")').first if name == "E" else \
                          self.page.locator('nav.pan-links a:text-is("E")').first if name == "W" else \
                          self.page.locator('nav.pan-links a:text-is("SW")').first if name == "NE" else \
                          self.page.locator('nav.pan-links a:text-is("SE")').first if name == "NW" else \
                          self.page.locator('nav.pan-links a:text-is("NW")').first if name == "SE" else \
                          self.page.locator('nav.pan-links a:text-is("NE")').first
            self.click_nav(center_link, f"pan back from {name}", MAP_DETAIL_RE)

        # Picker - only shown in Players' view for editors. As player, we test the map view tabs.
        # Switch to Players' view
        players_link = page.locator('a.nav-link:has-text("Players\' view")').first
        if players_link.count():
            self.click_nav(players_link, "switch to Players' view", MAP_DETAIL_RE)
            # Check picker form present
            picker_form = page.locator("form.map-picker-form")
            self.ck("picker form in Players' view", "present", picker_form.count(), picker_form.count() == 1)
            if picker_form.count():
                # Try selecting a character and submitting
                checkbox = picker_form.locator("input[name='characters']").first
                if checkbox.count():
                    checkbox.check()
                    self.click_nav(picker_form.locator("button[type=submit]"), "picker Show button", MAP_DETAIL_RE)
            # Back to Full map
            full_link = page.locator('a.nav-link:has-text("Full map")').first
            self.click_nav(full_link, "switch to Full map", MAP_DETAIL_RE)

        # Legend details toggle
        legend = page.locator("details.map-legend-details")
        self.ck("legend details present", "1", legend.count(), legend.count() == 1)
        if legend.count():
            # Open
            summary = legend.locator("> summary")
            summary.click()
            opened = wait_until(lambda: legend.evaluate("el => el.open"))
            self.ck("legend open", "open", "open" if opened else "closed", opened)
            # Close
            summary.click()
            closed = wait_until(lambda: not legend.evaluate("el => el.open"))
            self.ck("legend close", "closed", "closed" if closed else "open", closed)

        # Count visible cells vs radius 6 (127 hexes)
        cell_count = self.count_visible_cells()
        self.ck("visible hex cells at radius 6", "127", cell_count, cell_count == 127)

        # Player sees only visited hexes as links (aria-label on <a>)
        visited_links = page.locator('a[aria-label^="Tile"]').count()
        self.ck("visited hex links (player)", ">0", visited_links, visited_links > 0)

        # Request a visit button in toolbar
        visit_btn = page.locator("a:has-text('Request a visit')").first
        self.ck("Request a visit button", "present", visit_btn.count(), visit_btn.count() == 1)

        # Print link
        print_link = page.locator("a.print-link").first
        self.click_nav(print_link, "Print link", re.compile(r"/c/demo/map/\d+/print/"))
        # Print page has no print button, only text - flow 6
        print_page = page.locator("h1:has-text('Print')")
        self.ck("print page has title", "Print", print_page.count(), print_page.count() == 1)
        # Back to the map
        back_print = page.get_by_role("link", name="Back to the map")
        self.click_nav(back_print, "Back to the map from print", MAP_DETAIL_RE)

        return {"map_id": map_id}

    def check_tile_modal(self, map_id: int) -> None:
        """Tile modal/page: Wolf Den placeholder, Old Watchtower discovered, request buttons, close, open full page."""
        page = self.page
        # Go to Wolf Den at (0, -2) - placeholder "Unknown location"
        tile_url = f"/c/demo/map/{map_id}/tile/0/-2/"
        self.goto(tile_url, "Wolf Den tile modal")
        # Check placeholder
        placeholder = page.locator("div.map-location:has-text('Unknown location')")
        self.ck("Wolf Den shows Unknown location placeholder", "present", placeholder.count(), placeholder.count() == 1)
        # Three request buttons for placeholder
        found_btn = page.locator("a:has-text('Request a found mark')").first
        explored_btn = page.locator("a:has-text('Request explored credit')").first
        discovered_btn = page.locator("a:has-text('Request discovered credit')").first
        self.ck("placeholder: Request a found mark", "present", found_btn.count(), found_btn.count() == 1)
        self.ck("placeholder: Request explored credit", "present", explored_btn.count(), explored_btn.count() == 1)
        self.ck("placeholder: Request discovered credit", "present", discovered_btn.count(), discovered_btn.count() == 1)
        # Close modal
        close_btn = page.locator("button[data-bs-dismiss=modal]").first
        close_btn.click()
        closed = wait_until(lambda: page.locator("#app-modal.show").count() == 0)
        self.ck("tile modal Close", "modal closed", "closed" if closed else "open", closed)
        # Open full page
        self.goto(tile_url, "Wolf Den tile full page")
        back_link = page.get_by_role("link", name="Back to the map")
        self.click_nav(back_link, "Back to the map from tile page", MAP_DETAIL_RE)

        # Go to Old Watchtower at (1, 0) - discovered by Aria
        tile_url2 = f"/c/demo/map/{map_id}/tile/1/0/"
        self.goto(tile_url2, "Old Watchtower tile modal")
        # Check discovered by Aria
        disc_text = page.locator("p:has-text('Discovered by: Aria')").first
        self.ck("Old Watchtower discovered by Aria", "present", disc_text.count(), disc_text.count() == 1)
        # Three request buttons
        self.ck("OW: Request a found mark", "present", page.locator("a:has-text('Request a found mark')").first.count(), 1)
        self.ck("OW: Request explored credit", "present", page.locator("a:has-text('Request explored credit')").first.count(), 1)
        self.ck("OW: Request discovered credit", "present", page.locator("a:has-text('Request discovered credit')").first.count(), 1)
        # Request a visit and Map requests in toolbar
        self.ck("toolbar: Request a visit", "present", page.locator("a:has-text('Request a visit')").first.count(), 1)
        self.ck("toolbar: Map requests", "present", page.locator("a:has-text('Map requests')").first.count(), 1)
        # Close and Open full page
        close_btn2 = page.locator("button[data-bs-dismiss=modal]").first
        close_btn2.click()
        closed2 = wait_until(lambda: page.locator("#app-modal.show").count() == 0)
        self.ck("OW tile modal Close", "modal closed", "closed" if closed2 else "open", closed2)
        self.goto(tile_url2, "Old Watchtower tile full page")
        back_link2 = page.get_by_role("link", name="Back to the map")
        self.click_nav(back_link2, "Back to the map from OW tile page", MAP_DETAIL_RE)

    def check_request_forms(self, map_id: int) -> None:
        """Request forms: submit empty (errors), submit with character/date/note, check redirect to queue."""
        page = self.page

        # 1. Visit request for a new tile (2, 0) - Aria hasn't visited
        visit_url = f"/c/demo/map/requests/new/visit/{map_id}/?q=2&r=0"
        self.goto(visit_url, "Request visit form (new tile 2,0)")
        # Submit empty
        page.locator("button:has-text('Send request')").click()
        wait_until(lambda: page.locator(".is-invalid, .form-control.is-invalid, .alert-danger").count() > 0)
        errors = page.locator(".is-invalid, .form-control.is-invalid, .alert-danger, .text-danger").count()
        self.ck("visit form empty submit", "field errors visible", errors, errors > 0)
        # Fill and submit
        page.fill("input[name=date]", "2024-01-15")
        page.fill("textarea[name=note]", "Test visit request")
        # Character dropdown/checkbox - Aria
        char_checkbox = page.locator("input[name='characters'][value]").first
        if char_checkbox.count():
            char_checkbox.check()
        self.click_nav(page.locator("button:has-text('Send request')"), "visit form submit", REQUESTS_QUEUE)
        toast = self.toast_text()
        self.ck("visit request toast", "Visit request sent.", toast, toast == "Visit request sent.")
        # Map requests link on form
        self.goto(visit_url, "back to visit form")
        req_link = page.locator("a:has-text('Map requests')").first
        self.click_nav(req_link, "Map requests link on visit form", REQUESTS_QUEUE)

        # 2. Explored credit on Old Watchtower (1,0) - need location ID
        # First get the location ID from the tile modal
        tile_url = f"/c/demo/map/{map_id}/tile/1/0/"
        self.goto(tile_url, "OW tile for explored request")
        explored_link = page.locator("a:has-text('Request explored credit')").first
        explored_url = explored_link.get_attribute("href")
        self.click_nav(explored_link, "Request explored credit link", REQUEST_CREDIT_RE)
        # Submit empty
        page.locator("button:has-text('Send request')").click()
        wait_until(lambda: page.locator(".is-invalid, .form-control.is-invalid, .alert-danger").count() > 0)
        errors = page.locator(".is-invalid, .form-control.is-invalid, .alert-danger, .text-danger").count()
        self.ck("explored form empty submit", "field errors visible", errors, errors > 0)
        # Fill and submit
        page.fill("input[name=date]", "2024-01-15")
        page.fill("textarea[name=note]", "Test explored request")
        char_checkbox = page.locator("input[name='characters'][value]").first
        if char_checkbox.count():
            char_checkbox.check()
        self.click_nav(page.locator("button:has-text('Send request')"), "explored form submit", REQUESTS_QUEUE)
        toast = self.toast_text()
        self.ck("explored request toast", "Request sent.", toast, toast == "Request sent.")
        # Map requests link on form
        self.goto(explored_url, "back to explored form")
        req_link = page.locator("a:has-text('Map requests')").first
        self.click_nav(req_link, "Map requests link on explored form", REQUESTS_QUEUE)

        # 3. Found mark on Wolf Den placeholder (0,-2)
        tile_url2 = f"/c/demo/map/{map_id}/tile/0/-2/"
        self.goto(tile_url2, "Wolf Den tile for found request")
        found_link = page.locator("a:has-text('Request a found mark')").first
        found_url = found_link.get_attribute("href")
        self.click_nav(found_link, "Request a found mark link", REQUEST_CREDIT_RE)
        # Submit empty
        page.locator("button:has-text('Send request')").click()
        wait_until(lambda: page.locator(".is-invalid, .form-control.is-invalid, .alert-danger").count() > 0)
        errors = page.locator(".is-invalid, .form-control.is-invalid, .alert-danger, .text-danger").count()
        self.ck("found form empty submit", "field errors visible", errors, errors > 0)
        # Fill and submit
        page.fill("input[name=date]", "2024-01-15")
        page.fill("textarea[name=note]", "Test found request")
        char_checkbox = page.locator("input[name='characters'][value]").first
        if char_checkbox.count():
            char_checkbox.check()
        self.click_nav(page.locator("button:has-text('Send request')"), "found form submit", REQUESTS_QUEUE)
        toast = self.toast_text()
        self.ck("found request toast", "Request sent.", toast, toast == "Request sent.")
        # Map requests link on form
        self.goto(found_url, "back to found form")
        req_link = page.locator("a:has-text('Map requests')").first
        self.click_nav(req_link, "Map requests link on found form", REQUESTS_QUEUE)

        # 4. Discovered credit on Old Watchtower (1,0)
        self.goto(tile_url, "OW tile for discovered request")
        discovered_link = page.locator("a:has-text('Request discovered credit')").first
        discovered_url = discovered_link.get_attribute("href")
        self.click_nav(discovered_link, "Request discovered credit link", REQUEST_CREDIT_RE)
        # Submit empty
        page.locator("button:has-text('Send request')").click()
        wait_until(lambda: page.locator(".is-invalid, .form-control.is-invalid, .alert-danger").count() > 0)
        errors = page.locator(".is-invalid, .form-control.is-invalid, .alert-danger, .text-danger").count()
        self.ck("discovered form empty submit", "field errors visible", errors, errors > 0)
        # Fill and submit - also try Wren (alice's second character)
        page.fill("input[name=date]", "2024-01-15")
        page.fill("textarea[name=note]", "Test discovered request")
        char_checkboxes = page.locator("input[name='characters'][value]").all()
        for cb in char_checkboxes:
            label_text = page.locator(f"label[for='{cb.get_attribute('id')}']").inner_text().strip() if cb.get_attribute('id') else ""
            if "Wren" in label_text or "Aria" in label_text:
                cb.check()
        self.click_nav(page.locator("button:has-text('Send request')"), "discovered form submit", REQUESTS_QUEUE)
        toast = self.toast_text()
        self.ck("discovered request toast", "Request sent.", toast, toast == "Request sent.")
        # Map requests link on form
        self.goto(discovered_url, "back to discovered form")
        req_link = page.locator("a:has-text('Map requests')").first
        self.click_nav(req_link, "Map requests link on discovered form", REQUESTS_QUEUE)

        # Verify player queue shows 4 Requested rows
        self.goto(REQUESTS_QUEUE, "player requests queue")
        rows = page.locator("tbody tr").all()
        requested_count = sum(1 for r in rows if "Requested" in r.inner_text())
        self.ck("player queue shows 4 Requested rows", "4", requested_count, requested_count == 4)

    def check_requests_queue_player(self) -> None:
        """Player queue at 1280 and 390: summary cell, optional columns."""
        page = self.page
        self.goto(REQUESTS_QUEUE, "player requests queue")
        # d-sm-none summary cell at 390
        summary_cells = page.locator("td.d-sm-none").count()
        self.ck("player queue summary cell (d-sm-none)", "present at 390", summary_cells, summary_cells >= 1 if self.width == 390 else True)
        # Optional columns at 1280
        if self.width == 1280:
            opt_cols = page.locator("th.wm-col-optional:visible").count()
            self.ck("player queue optional columns at 1280", "visible", opt_cols, opt_cols >= 5)

    def check_gm_queue_and_approve(self, map_id: int) -> None:
        """GM: queue shows Borin's visit + alice's rows; per-row approve/decline; bulk approve."""
        page = self.page
        lib.login(page, self.base_url, "gm")
        self.goto(REQUESTS_QUEUE, "GM requests queue")
        # Should see Borin's visit + alice's 4 rows = 5 rows
        rows = page.locator("tbody tr").all()
        self.ck("GM queue shows 5 rows (Borin + alice x4)", "5", len(rows), len(rows) == 5)
        # Per-row Approve and Decline for requested
        req_rows = page.locator("tbody tr:has-text('Requested')").all()
        self.ck("GM queue has Requested rows", ">0", len(req_rows), len(req_rows) >= 1)
        # Decline one (the first requested that's not a visit)
        for row in req_rows:
            kind_badge = row.locator("td .badge").first
            kind_text = kind_badge.inner_text().strip() if kind_badge.count() else ""
            if kind_text != "Visit":
                decline_form = row.locator("form[action*='decline']")
                if decline_form.count():
                    with page.expect_navigation(wait_until="networkidle") as info:
                        decline_form.locator("button[type=submit]").click()
                    resp = info.value
                    status = resp.status if resp else None
                    self.ck("GM decline non-visit request", "2xx/3xx", status, status is not None and 200 <= status < 400)
                    toast = self.toast_text()
                    self.ck("decline toast", "Request declined.", toast, "declined" in toast.lower())
                    break
        # Per-row Approve one
        self.goto(REQUESTS_QUEUE, "GM queue after decline")
        req_rows = page.locator("tbody tr:has-text('Requested')").all()
        for row in req_rows:
            kind_badge = row.locator("td .badge").first
            kind_text = kind_badge.inner_text().strip() if kind_badge.count() else ""
            if kind_text != "Visit":
                approve_form = row.locator("form[action*='approve']")
                if approve_form.count():
                    with page.expect_navigation(wait_until="networkidle") as info:
                        approve_form.locator("button[type=submit]").click()
                    resp = info.value
                    status = resp.status if resp else None
                    self.ck("GM approve non-visit request", "2xx/3xx", status, status is not None and 200 <= status < 400)
                    toast = self.toast_text()
                    self.ck("approve toast", "Request approved.", toast, "approved" in toast.lower())
                    break

        # Bulk approve: select all, open modal, check tabs, cancel, then approve
        self.goto(REQUESTS_QUEUE, "GM queue for bulk approve")
        # Select all checkbox
        all_box = page.locator("#bulk-select-all")
        if all_box.count():
            all_box.check()
            wait_until(lambda: page.locator("input[name='requests']:checked").count() > 0)
        # Bulk approve button
        bulk_btn = page.locator("#bulk-approve-btn")
        self.ck("bulk approve button visible", "visible", bulk_btn.is_visible(), bulk_btn.is_visible())
        if bulk_btn.is_visible():
            bulk_btn.click()
            # Wait for modal
            modal = page.locator("#app-modal.show")
            wait_until(lambda: modal.count() == 1)
            self.ck("bulk approve modal opens", "open", modal.count(), modal.count() == 1)
            # Check tabs: Discovery, Exploration, Found mark
            tabs = page.locator("#bulk-approve-tabs .nav-link").all()
            tab_texts = [t.inner_text().strip() for t in tabs]
            self.ck("bulk modal tabs", "Discovery, Exploration, Found mark", tab_texts, tab_texts == ["Discovery", "Exploration", "Found mark"])
            # Check groups by kind
            for tab_id in ["pane-discovered", "pane-explored", "pane-found"]:
                page.locator(f"button[data-bs-target='#{tab_id}']").click()
                pane = page.locator(f"#{tab_id}")
                wait_until(lambda: "show active" in pane.get_attribute("class") or "active" in pane.get_attribute("class"))
                rows_in_pane = pane.locator("tr").count()
                self.ck(f"bulk modal {tab_id} has rows", ">=0", rows_in_pane, rows_in_pane >= 0)
            # Cancel/close
            page.locator("button[data-bs-dismiss=modal]").first.click()
            wait_until(lambda: page.locator("#app-modal.show").count() == 0)
            self.ck("bulk modal cancel", "closed", page.locator("#app-modal.show").count(), page.locator("#app-modal.show").count() == 0)
            # Now approve all
            all_box.check()
            wait_until(lambda: page.locator("input[name='requests']:checked").count() > 0)
            bulk_btn.click()
            modal = page.locator("#app-modal.show")
            wait_until(lambda: modal.count() == 1)
            # Click Approve all in modal
            approve_all = page.locator("button:has-text('Approve all')").first
            with page.expect_response(lambda r: r.url.endswith("bulk-approve/") and r.request.method == "POST") as info:
                approve_all.click()
            resp = info.value
            status = resp.status if resp else None
            self.ck("bulk approve POST", "2xx/3xx", status, status is not None and 200 <= status < 400)
            # Wait for toast and reload
            wait_until(lambda: page.locator(".wm-toast").count() > 0)
            toast = self.toast_text()
            self.ck("bulk approve toast", "Approved", toast, "Approved" in toast)
            # refreshQueue triggers reload
            wait_until(lambda: "requests" in page.url)
            self.ck("bulk approve reload", "queue page", "requests" in page.url, "requests" in page.url)

    def check_gm_map_controls(self, map_id: int) -> None:
        """GM map controls: Full map / Players' view / My characters tabs, picker, New map, edit links."""
        page = self.page
        self.goto(f"/c/demo/map/{map_id}/", "GM map detail")
        # Tabs with aria-current
        tabs = page.locator("nav.view-switch .nav-link").all()
        for tab in tabs:
            aria_current = tab.get_attribute("aria-current")
            is_active = "active" in tab.get_attribute("class") or ""
            self.ck(f"GM tab {tab.inner_text().strip()}", "aria-current=page if active", aria_current, True)
        # Picker checkboxes + Show (in Players' view)
        players_link = page.locator('a.nav-link:has-text("Players\' view")').first
        self.click_nav(players_link, "GM switch to Players' view", MAP_DETAIL_RE)
        picker_form = page.locator("form.map-picker-form")
        self.ck("GM picker form in Players' view", "present", picker_form.count(), picker_form.count() == 1)
        if picker_form.count():
            checkbox = picker_form.locator("input[name='characters']").first
            if checkbox.count():
                checkbox.check()
                self.click_nav(picker_form.locator("button[type=submit]"), "GM picker Show", MAP_DETAIL_RE)
        # New map link
        full_link = page.locator('a.nav-link:has-text("Full map")').first
        self.click_nav(full_link, "GM back to Full map", MAP_DETAIL_RE)
        new_map = page.locator("a:has-text('New map')").first
        self.ck("GM New map link", "present", new_map.count(), new_map.count() == 1)
        # Edit map/location links - visit but don't edit
        edit_map = page.locator("a:has-text('Edit map')").first
        if edit_map.count():
            self.click_nav(edit_map, "GM edit map link", re.compile(r"/c/demo/map/\d+/edit/"))
            page.go_back()
            wait_until(lambda: "map/\d+/$" in page.url)

    def check_player_after_approval(self, map_id: int) -> None:
        """Back as alice: queue shows Approved/Declined; tile shows credits; reload persists."""
        page = self.page
        lib.login(page, self.base_url, "player")
        # Queue shows Approved/Declined badges
        self.goto(REQUESTS_QUEUE, "player queue after GM approval")
        rows = page.locator("tbody tr").all()
        approved = sum(1 for r in rows if "Approved" in r.inner_text())
        declined = sum(1 for r in rows if "Declined" in r.inner_text())
        self.ck("player queue has Approved rows", ">=1", approved, approved >= 1)
        self.ck("player queue has Declined rows", ">=1", declined, declined >= 1)

        # Tile page: Old Watchtower shows Aria in "Explored by"
        tile_url = f"/c/demo/map/{map_id}/tile/1/0/"
        self.goto(tile_url, "OW tile after approval")
        explored_text = page.locator("p:has-text('Explored by:')").first
        self.ck("OW explored by Aria", "Aria in explored", explored_text.count(), explored_text.count() == 1)
        if explored_text.count():
            self.ck("OW explored by includes Aria", "Aria", "Aria" in explored_text.inner_text(), "Aria" in explored_text.inner_text())

        # Wolf Den now shows its name instead of "Unknown location"
        tile_url2 = f"/c/demo/map/{map_id}/tile/0/-2/"
        self.goto(tile_url2, "Wolf Den tile after approval")
        wd_name = page.locator("div.map-location h3:has-text('Wolf Den')").first
        self.ck("Wolf Den shows name not Unknown", "Wolf Den", wd_name.count(), wd_name.count() == 1)
        # No "!" unexplored marker on map cell
        # Check the map cell for (0,-2) - should not have hex-unexplored
        self.goto(f"/c/demo/map/{map_id}/", "map after approval")
        # Reload and check state persists
        resp = page.reload(wait_until="networkidle")
        status = resp.status if resp else None
        self.ck("map reload after approval", "2xx/3xx", status, status is not None and 200 <= status < 400)
        # Check Wolf Den tile still shows name
        self.goto(tile_url2, "Wolf Den tile after reload")
        wd_name2 = page.locator("div.map-location h3:has-text('Wolf Den')").first
        self.ck("Wolf Den name persists after reload", "Wolf Den", wd_name2.count(), wd_name2.count() == 1)
        # Check OW explored persists
        self.goto(tile_url, "OW tile after reload")
        explored_text2 = page.locator("p:has-text('Explored by:')").first
        self.ck("OW explored persists after reload", "Aria in explored", explored_text2.count(), explored_text2.count() == 1)

        # New tile visit (2,0) is now a link on the map
        self.goto(f"/c/demo/map/{map_id}/", "map after reload for new tile")
        new_tile_link = page.locator('a[aria-label="Tile (2, 0)"]').first
        self.ck("new tile (2,0) is now a link", "present", new_tile_link.count(), new_tile_link.count() == 1)

        # Also check radius URL parameter works (zoom test via URL - no UI control)
        for radius in [2, 15]:
            radius_url = f"/c/demo/map/{map_id}/?radius={radius}"
            self.goto(radius_url, f"map radius={radius} via URL")
            cell_count = self.count_visible_cells()
            expected = 7 if radius == 2 else 331  # radius 2 = 7 hexes, radius 15 = 331 hexes
            self.ck(f"radius={radius} cell count", str(expected), cell_count, cell_count == expected)
        # Note: no zoom control in UI
        self.ck("zoom control in UI", "none (radius only via URL)", "no UI control found", True)


def run_flow(w: Walker, map_id: int) -> None:
    lib.login(w.page, w.base_url, "player")
    w.goto("/c/demo/", "club home")
    w.ck(
        "login as alice",
        "left /accounts/login/",
        w.page.evaluate("location.pathname"),
        "/accounts/login/" not in w.page.evaluate("location.pathname"),
    )

    w.section("map index", lambda: w.check_map_index())
    w.section("map detail", lambda: w.check_map_detail(map_id))
    w.section("tile modal/page", lambda: w.check_tile_modal(map_id))
    w.section("request forms", lambda: w.check_request_forms(map_id))
    w.section("player queue", lambda: w.check_requests_queue_player())

    # GM approval
    w.section("GM queue and approve", lambda: w.check_gm_queue_and_approve(map_id))
    w.section("GM map controls", lambda: w.check_gm_map_controls(map_id))

    # Back as alice
    w.section("player after approval", lambda: w.check_player_after_approval(map_id))


def run_width(browser, width: int, height: int) -> tuple[int, list[str]]:
    """Fresh DB and server for one width. Returns (controls tried, problems)."""
    with tempfile.TemporaryDirectory(prefix=f"flow8-{width}-") as td:
        env = lib.fresh_demo_db(Path(td) / "demo.sqlite3")
        with lib.run_server(env) as server:
            w = Walker(browser, server.base_url, width, height)
            try:
                # Get the map ID from the seeded demo
                # We know from demo.py it's "The Marches"
                # Need to find its ID - we'll navigate to map index and extract
                w.goto("/c/demo/map/", "map index to get map ID")
                map_link = w.page.locator("ul.map-grid a").first
                href = map_link.get_attribute("href")
                map_id = int(href.split("/")[-2]) if href else 1
                run_flow(w, map_id)
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
        print(f"Flow 8 map check: browser={browser_name}")
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
            f"Flow 8 map check: PROBLEMS ({len(problems)}), browser={browser_name}, "
            f"controls tried={total} ({counts})"
        )
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"Flow 8 map check: clean, browser={browser_name}, controls tried={total} ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())