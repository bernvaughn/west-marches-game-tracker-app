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
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
REQUEST_CREDIT_RE = re.compile(
    r"/c/demo/map/requests/new/(discovered|explored|found)/location/\d+/"
)
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


OPPOSITE = {"E": "W", "W": "E", "NE": "SW", "SW": "NE", "NW": "SE", "SE": "NW"}
DIRECTIONS = {"E": (1, 0), "W": (-1, 0), "NE": (1, -1), "NW": (0, -1), "SE": (0, 1), "SW": (-1, 1)}
DEFAULT_RADIUS = 6
NOTES = {
    "visit": "f8-visit",
    "explored": "f8-explored",
    "found": "f8-found",
    "discovered": "f8-discovered",
}


def hex_count(radius: int) -> int:
    """Number of hexes in a hex-shaped window of the given radius."""
    return 1 + 3 * radius * (radius + 1)


def parse_window_url(url: str) -> tuple[int, int, int]:
    """Read (q, r, radius) from a map URL, with the app's defaults (0, 0, 6)."""
    params = parse_qs(urlparse(url).query)

    def num(key: str, default: int) -> int:
        try:
            return int(params[key][0])
        except (KeyError, ValueError, IndexError):
            return default

    return num("q", 0), num("r", 0), num("radius", DEFAULT_RADIUS)


def expected_pan(name: str, q: int, r: int, radius: int) -> tuple[int, int]:
    """Where a pan link of the given direction should land."""
    dq, dr = DIRECTIONS[name]
    return q + dq * radius, r + dr * radius


ERRORS = ".errorlist, .invalid-feedback, .is-invalid"


class Walker:
    """One browser session at one width, logging every control through a Recorder."""

    def __init__(self, browser, base_url: str, width: int, height: int) -> None:
        self.browser = browser
        self.base_url = base_url
        self.width = width
        self.height = height
        self.rec = lib.Recorder()
        self.ctx = None
        self.page = None
        self._open_context()

    def _open_context(self) -> None:
        self.ctx = self.browser.new_context(viewport={"width": self.width, "height": self.height})
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(8000)
        self.rec.attach(self.page)

    def new_session(self, role: str) -> None:
        """Drop the current browser context (and its login) and log in as ``role``.

        Logout is POST-only, so a fresh context per role is the clean switch.
        """
        self.ctx.close()
        self._open_context()
        lib.login(self.page, self.base_url, role)

    # -- logging ---------------------------------------------------------

    def ck(self, control: str, expected, actual, ok) -> bool:
        self.rec.check(FLOW, self.page.url, f"{control} @{self.width}", expected, actual, bool(ok))
        return bool(ok)

    def section(self, name: str, fn) -> None:
        """Run one section. A crash is recorded as a failed check, not hidden."""
        print(f"  section: {name}", flush=True)
        try:
            fn()
        except Exception as exc:
            self.ck(f"section {name}", "completes", f"{type(exc).__name__}: {exc}"[:300], False)

    # -- navigation ------------------------------------------------------

    def goto(self, path: str, control: str) -> bool:
        resp = self.page.goto(f"{self.base_url}{path}", wait_until="networkidle")
        status = resp.status if resp else None
        return self.ck(control, "2xx/3xx", status, status is not None and 200 <= status < 400)

    def reload(self, control: str) -> bool:
        resp = self.page.reload(wait_until="networkidle")
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
        """Text of the first flash message (a plain Django message is an inline alert)."""
        loc = self.page.locator("ul.wm-messages li.wm-alert")
        if not wait_until(lambda: loc.count() > 0, 8):
            return ""
        return loc.first.inner_text().strip()

    def has_text(self, control: str, text: str, scope=None) -> bool:
        loc = (scope or self.page).get_by_text(text).first
        return self.ck(control, f"{text!r} visible", loc.count(), loc.count() > 0)

    def count_cells(self) -> int:
        """Hex cells in the SVG map (one <g> per cell)."""
        return self.page.locator(".hexmap svg g").count()

    def modal_shown(self) -> bool:
        return bool(wait_until(lambda: self.page.locator("#app-modal.show").count() == 1))

    def modal_hidden(self) -> bool:
        return bool(wait_until(lambda: self.page.locator("#app-modal.show").count() == 0))

    def open_tile_modal(self, q: int, r: int, control: str) -> bool:
        """Click a hex cell on the map page and wait for the shared modal."""
        cell = self.page.locator(f'a[aria-label^="Tile ({q}, {r})"]').first
        if not cell.count():
            return self.ck(control, "cell is a link", "no link for this cell", False)
        cell.click()
        shown = self.modal_shown()
        title = ""
        if shown:
            title = self.page.locator("#app-modal .modal-title").inner_text()
        return self.ck(
            control, f"modal open for ({q}, {r})", title, shown and f"({q}, {r})" in title
        )

    def char_box(self, name: str, scope=None):
        """The checkbox of the character called ``name`` (request form by default)."""
        scope = scope or self.page.locator("form.wm-form")
        return scope.get_by_label(name).first

    def pick_only(self, name: str, scope) -> None:
        boxes = scope.locator("input[name=characters]")
        for i in range(boxes.count()):
            boxes.nth(i).uncheck()
        self.char_box(name, scope).check()

    def check_player_picker(self) -> None:
        """The player's own picker: 'Show the map for' one character, then Show."""
        page = self.page
        picker = page.locator("form.map-picker-form")
        self.ck("player picker form", "1", picker.count(), picker.count() == 1)
        names = [t.strip() for t in picker.locator("label").all_inner_texts()]
        self.ck(
            "picker lists Aria and Wren",
            "Aria, Wren",
            names,
            any("Aria" in n for n in names) and any("Wren" in n for n in names),
        )
        self.pick_only("Wren", picker)
        self.click_nav(
            picker.get_by_role("button", name="Show"), "picker Show (Wren)", MAP_DETAIL_RE
        )
        links = page.locator('a[aria-label^="Tile (1, 0)"]').count()
        self.ck("Wren has not visited (1, 0)", "0", links, links == 0)
        wren = self.char_box("Wren", page.locator("form.map-picker-form")).is_checked()
        self.ck("picker choice survives Show", "Wren ticked", wren, wren)
        self.reload("picker reload")
        wren = self.char_box("Wren", page.locator("form.map-picker-form")).is_checked()
        self.ck("picker choice survives reload", "Wren ticked", wren, wren)
        # Back to Aria so the rest of the flow sees her tiles.
        picker = page.locator("form.map-picker-form")
        self.pick_only("Aria", picker)
        self.click_nav(
            picker.get_by_role("button", name="Show"), "picker Show (Aria)", MAP_DETAIL_RE
        )
        links = page.locator('a[aria-label^="Tile (1, 0)"]').count()
        self.ck("Aria has visited (1, 0)", "1", links, links == 1)

    # -- sections --------------------------------------------------------

    def check_map_index(self) -> None:
        """Map list: map link, XP table, Map requests, no New map for a player."""
        page = self.page
        self.nav_to("All maps", MAP_INDEX, "All maps")
        map_link = page.locator("ul.map-grid a").first
        self.ck(
            "map list shows The Marches",
            "The Marches",
            map_link.inner_text().strip(),
            "The Marches" in map_link.inner_text(),
        )
        self.click_nav(map_link, "map link: The Marches", MAP_DETAIL_RE)
        self.click_nav(page.get_by_role("link", name="Back to maps"), "Back to maps", MAP_INDEX)
        self.click_nav(
            page.get_by_role("link", name="XP table").first,
            "XP table link",
            re.compile(r"/map/xp/"),
        )
        self.click_nav(
            page.get_by_role("link", name="Back to maps"), "Back to maps from XP table", MAP_INDEX
        )
        self.click_nav(
            page.get_by_role("link", name="Map requests").first, "Map requests link", REQUESTS_QUEUE
        )
        self.click_nav(page.get_by_role("link", name="Back to maps"), "Back to maps", MAP_INDEX)
        new_map = page.locator("a:has-text('New map')")
        self.ck("no New map button for player", "hidden", new_map.count(), new_map.count() == 0)

    def check_map_detail(self, map_id: int) -> None:
        """Map detail: legend, pan links, cells, visit button, print link, zoom by URL."""
        page = self.page
        detail = f"/c/demo/map/{map_id}/"
        self.goto(detail, "map detail")

        legend = page.locator("details.map-legend-details")
        self.ck("legend present", "1", legend.count(), legend.count() == 1)
        if legend.count():
            summary = legend.locator("> summary")
            is_open = legend.evaluate("el => el.open")
            self.ck("legend starts open", "open", "open" if is_open else "closed", is_open)
            summary.click()
            closed = wait_until(lambda: not legend.evaluate("el => el.open"))
            self.ck("legend toggle closes", "closed", "closed" if closed else "open", closed)
            summary.click()
            opened = wait_until(lambda: legend.evaluate("el => el.open"))
            self.ck("legend toggle opens", "open", "open" if opened else "closed", opened)

        cells = self.count_cells()
        self.ck("hex cells at default radius", hex_count(6), cells, cells == hex_count(6))
        links = page.locator('a[aria-label^="Tile"]').count()
        self.ck("player sees visited hexes as links", ">0", links, links > 0)
        tabs = page.locator("nav.view-switch").count()
        self.ck("no view tabs for a player", "0", tabs, tabs == 0)
        self.check_player_picker()
        visit_btn = page.get_by_role("link", name="Request a visit")
        self.ck("Request a visit button", "present", visit_btn.count(), visit_btn.count() == 1)

        pan = page.locator("nav.pan-links a")
        names = [t.strip() for t in pan.all_inner_texts()]
        self.ck("pan links", "E W NE NW SE SW", " ".join(names), sorted(names) == sorted(OPPOSITE))
        for name in names:
            self.click_nav(
                page.locator(f'nav.pan-links a:text-is("{name}")'), f"pan {name}", MAP_DETAIL_RE
            )
            got = parse_window_url(page.url)
            want = expected_pan(name, 0, 0, DEFAULT_RADIUS) + (DEFAULT_RADIUS,)
            self.ck(f"pan {name} window", want, got, got == want)
            cells = self.count_cells()
            self.ck(f"pan {name} keeps all cells", hex_count(6), cells, cells == hex_count(6))
            self.reload(f"pan {name} reload")
            got = parse_window_url(page.url)
            self.ck(f"pan {name} window survives reload", want, got, got == want)
            self.click_nav(
                page.locator(f'nav.pan-links a:text-is("{OPPOSITE[name]}")'),
                f"pan back {OPPOSITE[name]}",
                MAP_DETAIL_RE,
            )
            got = parse_window_url(page.url)
            self.ck(f"pan {name} then back", (0, 0, 6), got, got == (0, 0, 6))

        # There is no zoom control; radius is read from the URL only. Note it.
        zoom = page.locator("[aria-label*=zoom i], button:has-text('Zoom'), a:has-text('Zoom')")
        self.ck("zoom control in the UI", "none (note, not a failure)", zoom.count(), True)
        for radius in (2, 15):
            self.goto(f"{detail}?radius={radius}", f"map radius={radius} by URL")
            cells = self.count_cells()
            self.ck(
                f"radius {radius} cell count", hex_count(radius), cells, cells == hex_count(radius)
            )

        self.goto(detail, "map detail again")
        self.click_nav(
            page.locator("a.print-link"), "Print link", re.compile(r"/c/demo/map/\d+/print/")
        )
        title = page.title()
        self.ck("print page title", "contains '(print)'", title, "(print)" in title)
        self.click_nav(
            page.get_by_role("link", name="Back to the map"),
            "Back to the map from print",
            MAP_DETAIL_RE,
        )

    def check_tile_modal(self, map_id: int) -> None:
        """Hex cells open the shared modal; Close, X, Open full page, tile page."""
        page = self.page
        detail = f"/c/demo/map/{map_id}/"
        self.goto(detail, "map detail for tiles")

        # Old Watchtower (1, 0): discovered by Aria.
        self.open_tile_modal(1, 0, "hex cell (1, 0) opens modal")
        modal = page.locator("#app-modal")
        self.has_text("modal: Old Watchtower", "Old Watchtower", modal)
        self.has_text("modal: Discovered by Aria", "Discovered by: Aria", modal)
        for label in (
            "Request a found mark",
            "Request explored credit",
            "Request discovered credit",
            "Request a visit",
        ):
            self.has_text(f"modal: {label}", label, modal)
        page.locator("#app-modal .modal-footer button[data-bs-dismiss=modal]").click()
        self.ck("modal footer Close", "modal closed", self.modal_hidden(), self.modal_hidden())

        self.open_tile_modal(1, 0, "hex cell (1, 0) reopens modal")
        page.locator("#app-modal .btn-close").click()
        self.ck("modal X button", "modal closed", self.modal_hidden(), self.modal_hidden())

        self.open_tile_modal(1, 0, "hex cell (1, 0) opens modal for full page")
        self.click_nav(
            page.locator("#app-modal a:text-is('Open full page')"),
            "modal Open full page",
            TILE_PAGE_RE,
        )
        self.has_text("tile page: Old Watchtower", "Old Watchtower")
        self.has_text("tile page: Discovered by Aria", "Discovered by: Aria")
        self.has_text("tile page: Request a visit", "Request a visit")
        self.click_nav(
            page.get_by_role("link", name="Back to the map"),
            "tile page Back to the map",
            MAP_DETAIL_RE,
        )

        # Wolf Den (0, -2): Aria visited it, but nobody discovered it, so she sees nothing.
        self.open_tile_modal(0, -2, "hex cell (0, -2) opens modal")
        self.has_text("modal: nothing here yet", "Nothing here yet", modal)
        wolf = page.get_by_text("Wolf Den").count()
        self.ck("modal hides the Wolf Den name", "0", wolf, wolf == 0)
        page.locator("#app-modal .modal-footer button[data-bs-dismiss=modal]").click()
        self.modal_hidden()

    def request_form(
        self, control: str, kind: str, characters: list[str], toast: str, fix_coords=None
    ) -> None:
        """On a request form: submit with no character, then fill, send, check the flash message."""
        page = self.page
        self.ck(
            f"{control}: date defaults",
            "non-empty",
            page.input_value("input[name=date]"),
            page.input_value("input[name=date]") != "",
        )
        # Wren is not ticked by default; Aria is. Clear everything and send.
        boxes = page.locator("input[name=characters]")
        for i in range(boxes.count()):
            boxes.nth(i).uncheck()
        page.get_by_role("button", name="Send request").click()
        shown = wait_until(lambda: page.locator(ERRORS).count() > 0)
        self.ck(
            f"{control}: send with no character",
            "field error visible",
            bool(shown),
            bool(shown) and "/new/" in page.url,
        )
        for name in characters:
            self.char_box(name).check()
        if fix_coords:
            page.fill("input[name=q]", str(fix_coords[0]))
            page.fill("input[name=r]", str(fix_coords[1]))
        page.fill("textarea[name=note]", NOTES[kind])
        self.click_nav(
            page.get_by_role("button", name="Send request"),
            f"{control}: send request",
            REQUESTS_QUEUE,
        )
        got = self.toast_text()
        self.ck(f"{control}: flash message", toast, got, got == toast)

    def check_request_forms(self, map_id: int) -> None:
        """Four requests from the real tile pages: visit, explored, found, discovered."""
        page = self.page
        # Visit: from the tile page toolbar, then move the position to a new tile.
        self.goto(f"/c/demo/map/{map_id}/tile/1/0/", "Old Watchtower tile page")
        self.click_nav(
            page.get_by_role("link", name="Request a visit"),
            "tile page Request a visit",
            REQUEST_VISIT_RE,
        )
        self.request_form("visit", "visit", ["Aria"], "Visit request sent.", fix_coords=(2, 0))

        self.goto(f"/c/demo/map/{map_id}/tile/1/0/", "Old Watchtower tile page")
        self.click_nav(
            page.get_by_role("link", name="Request explored credit"),
            "tile page Request explored credit",
            REQUEST_CREDIT_RE,
        )
        self.request_form("explored", "explored", ["Aria"], "Request sent.")

        # Found mark for Wren only; approval also records her visit to the tile.
        self.goto(f"/c/demo/map/{map_id}/tile/1/0/", "Old Watchtower tile page")
        self.click_nav(
            page.get_by_role("link", name="Request a found mark"),
            "tile page Request a found mark",
            REQUEST_CREDIT_RE,
        )
        self.request_form("found", "found", ["Wren"], "Request sent.")

        self.goto(f"/c/demo/map/{map_id}/tile/1/0/", "Old Watchtower tile page")
        self.click_nav(
            page.get_by_role("link", name="Request discovered credit"),
            "tile page Request discovered credit",
            REQUEST_CREDIT_RE,
        )
        # Both of alice's characters on one request.
        self.request_form("discovered", "discovered", ["Aria", "Wren"], "Request sent.")

        # The Map requests link on a form.
        self.goto(f"/c/demo/map/requests/new/visit/{map_id}/", "visit form")
        self.click_nav(
            page.get_by_role("link", name="Map requests"), "form Map requests link", REQUESTS_QUEUE
        )
        self.goto(REQUESTS_QUEUE, "player queue")
        for kind, note in NOTES.items():
            row = page.locator("tbody tr").filter(has_text=note)
            self.ck(
                f"queue row for {kind}",
                "Requested",
                row.count(),
                row.count() == 1 and "Requested" in row.inner_text(),
            )
        boxes = page.locator("input[name=requests]").count()
        self.ck("player has no select checkboxes", "0", boxes, boxes == 0)
        acts = page.locator("tbody form").count()
        self.ck("player has no approve or decline buttons", "0", acts, acts == 0)

    def check_requests_queue_player(self) -> None:
        """Player queue at 1280 and 390: summary cell or optional columns."""
        page = self.page
        self.goto(REQUESTS_QUEUE, "player requests queue")
        summary = page.locator("td.wm-req-summary:visible").count()
        optional = page.locator("th.wm-col-optional:visible").count()
        if self.width == 390:
            self.ck("queue summary cell shows", ">=1", summary, summary >= 1)
            self.ck("queue optional columns hidden", "0", optional, optional == 0)
        else:
            self.ck("queue summary cell hidden", "0", summary, summary == 0)
            self.ck("queue optional columns show", ">=5", optional, optional >= 5)

    def gm_row(self, kind: str):
        return self.page.locator("tbody tr").filter(has_text=NOTES[kind])

    def gm_decide(self, kind: str, action: str, toast: str) -> None:
        """Click the per-row Approve or Decline button of one of alice's requests."""
        page = self.page
        row = self.gm_row(kind)
        button = row.locator(f"form[action*='{action}'] button[type=submit]")
        self.click_nav(button, f"GM {action} {kind} request", REQUESTS_QUEUE)
        got = self.toast_text()
        self.ck(f"GM {action} {kind} flash message", toast, got, got == toast)
        self.reload(f"GM {action} {kind} reload")
        text = self.gm_row(kind).inner_text()
        want = "Approved" if action == "approve" else "Declined"
        self.ck(f"GM {kind} status after reload", want, text[:60], want in text)
        assert page is self.page

    def check_gm_queue_and_approve(self) -> None:
        """GM: sees Borin's visit and alice's four rows; decline, approve, bulk approve."""
        page = self.page
        self.goto(REQUESTS_QUEUE, "GM requests queue")
        rows = page.locator("tbody tr").count()
        self.ck("GM queue rows (Borin + alice x4)", 5, rows, rows == 5)
        self.ck(
            "GM select-all checkbox",
            "present",
            page.locator("#bulk-select-all").count(),
            page.locator("#bulk-select-all").count() == 1,
        )
        bulk_btn = page.locator("#bulk-approve-btn")
        self.ck(
            "bulk button hidden with nothing ticked",
            "hidden",
            bulk_btn.is_visible(),
            not bulk_btn.is_visible(),
        )

        self.gm_decide("visit", "approve", "Request approved.")
        self.gm_decide("discovered", "decline", "Request declined.")
        self.gm_decide("explored", "approve", "Request approved.")

        # Per-row checkbox shows the bulk button with a count.
        found_box = self.gm_row("found").locator("input[name=requests]")
        found_box.check()
        shown = wait_until(lambda: bulk_btn.is_visible())
        count = page.locator("#bulk-count").inner_text()
        self.ck(
            "row checkbox shows bulk button",
            "Approve selected (1)",
            f"{shown} {count}",
            shown and count == "1",
        )
        found_box.uncheck()
        hidden = wait_until(lambda: not bulk_btn.is_visible())
        self.ck("unticking hides bulk button", "hidden", bool(hidden), bool(hidden))

        # Select all, open the modal, look at each tab, cancel.
        page.locator("#bulk-select-all").check()
        wait_until(lambda: bulk_btn.is_visible())
        bulk_btn.click()
        self.ck("bulk modal opens", "open", self.modal_shown(), self.modal_shown())
        tabs = [t.strip() for t in page.locator("#bulk-approve-tabs .nav-link").all_inner_texts()]
        self.ck(
            "bulk modal tabs",
            "Discovery, Exploration, Found mark",
            tabs,
            tabs == ["Discovery", "Exploration", "Found mark"],
        )
        # Only the found request is still open, so only the Found mark tab has a row.
        rows_per_tab = {"explored": 0, "found": 1, "discovered": 0}
        for tab_id, want in rows_per_tab.items():
            page.locator(f"#tab-{tab_id}").click()
            active = wait_until(
                lambda t=tab_id: (
                    "active" in (page.locator(f"#pane-{t}").get_attribute("class") or "")
                )
            )
            self.ck(f"bulk modal {tab_id} tab", "pane active", bool(active), bool(active))
            rows = page.locator(f"#pane-{tab_id} tbody tr:not(:has(td[colspan]))").count()
            self.ck(f"bulk modal {tab_id} rows", want, rows, rows == want)
        page.locator("#app-modal .modal-footer button[data-bs-dismiss=modal]").click()
        self.ck("bulk modal Cancel", "closed", self.modal_hidden(), self.modal_hidden())
        ticked = page.locator("input[name=requests]:checked").count()
        self.ck("rows stay ticked after Cancel", ">=1", ticked, ticked >= 1)

        # Open again and approve.
        bulk_btn.click()
        self.modal_shown()
        with page.expect_response(
            lambda r: r.url.endswith("bulk-approve/") and r.request.method == "POST"
        ) as info:
            page.locator("#app-modal .modal-footer button[type=submit]").click()
        status = info.value.status
        self.ck("bulk approve POST", "2xx/3xx", status, 200 <= status < 400)
        # KNOWN APP BUG (filed under the epic): the 204 has no swap, so htmx never fires
        # afterSwap and the queue is not reloaded. This check fails until that is fixed.
        loaded = wait_until(
            lambda: (
                page.locator("#bulk-approve-btn").count() == 1
                and "Approved" in self.gm_row("found").inner_text()
            ),
            15,
        )
        self.ck(
            "bulk approve reloads the queue by itself",
            "found request Approved without a manual reload",
            bool(loaded),
            bool(loaded),
        )
        self.reload("bulk approve reload")
        text = self.gm_row("found").inner_text()
        self.ck(
            "found request Approved after reload",
            "Approved",
            "Approved" in text,
            "Approved" in text,
        )
        left = page.locator("input[name=requests]").count()
        # Bulk approve skips visit requests, so Borin's visit is the one row left.
        self.ck("only Borin's visit is left to tick", 1, left, left == 1)

    def check_gm_map_controls(self, map_id: int) -> None:
        """GM map controls: view tabs, picker, New map and edit links. No data edits."""
        page = self.page
        self.goto(f"/c/demo/map/{map_id}/", "GM map detail")
        current = page.locator("nav.view-switch a[aria-current=page]").inner_text()
        self.ck("GM Full map tab current", "Full map", current, current.strip() == "Full map")
        self.click_nav(
            page.locator('nav.view-switch a:text-is("Players\' view")'),
            "GM Players' view tab",
            MAP_DETAIL_RE,
        )
        current = page.locator("nav.view-switch a[aria-current=page]").inner_text()
        self.ck(
            "GM Players' view tab current",
            "Players' view",
            current,
            current.strip() == "Players' view",
        )
        picker = page.locator("form.map-picker-form")
        self.ck("GM picker form", "1", picker.count(), picker.count() == 1)
        boxes = picker.locator("input[name=characters]")
        self.ck("GM picker has characters", ">=1", boxes.count(), boxes.count() >= 1)
        if boxes.count():
            boxes.first.check()
            self.click_nav(
                picker.get_by_role("button", name="Show"), "GM picker Show", MAP_DETAIL_RE
            )
            ticked = page.locator("form.map-picker-form input[name=characters]:checked").count()
            self.ck("picker choice survives Show", ">=1", ticked, ticked >= 1)
            self.reload("picker reload")
            ticked = page.locator("form.map-picker-form input[name=characters]:checked").count()
            self.ck("picker choice survives reload", ">=1", ticked, ticked >= 1)
        mine = page.locator("nav.view-switch a:text-is('My characters')")
        if mine.count():
            self.click_nav(mine, "GM My characters tab", MAP_DETAIL_RE)
        self.click_nav(
            page.locator("nav.view-switch a:text-is('Full map')"), "GM Full map tab", MAP_DETAIL_RE
        )
        edit = page.get_by_role("link", name=re.compile("Edit map|Edit this map"))
        if edit.count():
            self.click_nav(edit.first, "GM edit map link", re.compile(r"/c/demo/map/\d+/edit/"))
            self.goto(f"/c/demo/map/{map_id}/", "GM map detail again")
        self.goto(MAP_INDEX, "GM map list")
        new_map = page.get_by_role("link", name="New map")
        self.ck("GM sees New map", "1", new_map.count(), new_map.count() == 1)
        if new_map.count():
            self.click_nav(new_map, "GM New map link", re.compile(r"/c/demo/map/new/"))

    def check_player_after_approval(self, map_id: int) -> None:
        """Back as alice: Approved/Declined badges and the credit on tile and map; reload."""
        page = self.page
        self.goto(REQUESTS_QUEUE, "player queue after approval")
        want = {
            "visit": "Approved",
            "explored": "Approved",
            "found": "Approved",
            "discovered": "Declined",
        }
        for kind, status in want.items():
            text = page.locator("tbody tr").filter(has_text=NOTES[kind]).inner_text()
            self.ck(f"alice {kind} request {status}", status, status in text, status in text)

        tile = f"/c/demo/map/{map_id}/tile/1/0/"
        for label in ("after approval", "after reload"):
            if label == "after reload":
                self.reload("OW tile reload")
            else:
                self.goto(tile, "Old Watchtower tile page")
            text = page.locator("p:has-text('Explored by:')").first.inner_text()
            self.ck(f"credit shows: OW explored by Aria {label}", "Aria", text, "Aria" in text)

        # Found mark approved for Wren: her view of the map now has (1, 0) and its name.
        self.goto(f"/c/demo/map/{map_id}/", "map after approval")
        picker = page.locator("form.map-picker-form")
        self.pick_only("Wren", picker)
        self.click_nav(
            picker.get_by_role("button", name="Show"), "picker Show (Wren)", MAP_DETAIL_RE
        )
        for label in ("after approval", "after reload"):
            if label == "after reload":
                self.reload("Wren map reload")
            link = page.locator('a[aria-label^="Tile (1, 0)"]').count()
            self.ck(f"credit shows: Wren sees (1, 0) {label}", "1", link, link == 1)
        self.open_tile_modal(1, 0, "Wren hex cell (1, 0) opens modal")
        self.has_text(
            "credit shows: Wren sees Old Watchtower", "Old Watchtower", page.locator("#app-modal")
        )
        page.locator("#app-modal .modal-footer button[data-bs-dismiss=modal]").click()
        self.modal_hidden()

        # The approved visit: (2, 0) is now a link on Aria's map.
        self.goto(f"/c/demo/map/{map_id}/", "Aria map after approval")
        for label in ("after approval", "after reload"):
            if label == "after reload":
                self.reload("Aria map reload")
            new_tile = page.locator('a[aria-label^="Tile (2, 0)"]').count()
            self.ck(
                f"credit shows: visit tile (2, 0) is a link {label}", "1", new_tile, new_tile == 1
            )


def run_flow(w: Walker, map_id: int) -> None:
    w.section("map index", w.check_map_index)
    w.section("map detail", lambda: w.check_map_detail(map_id))
    w.section("tile modal and page", lambda: w.check_tile_modal(map_id))
    w.section("request forms", lambda: w.check_request_forms(map_id))
    w.section("player queue", w.check_requests_queue_player)

    w.new_session("gm")
    w.section("GM queue and approve", w.check_gm_queue_and_approve)
    w.section("GM map controls", lambda: w.check_gm_map_controls(map_id))

    w.new_session("player")
    w.section("player after approval", lambda: w.check_player_after_approval(map_id))


def run_width(browser, width: int, height: int) -> tuple[int, list[str]]:
    """Fresh DB and server for one width. Returns (controls tried, problems)."""
    with tempfile.TemporaryDirectory(prefix=f"flow8-{width}-") as td:
        env = lib.fresh_demo_db(Path(td) / "demo.sqlite3")
        with lib.run_server(env) as server:
            w = Walker(browser, server.base_url, width, height)
            try:
                lib.login(w.page, w.base_url, "player")
                w.goto("/c/demo/map/", "map list")
                href = w.page.locator("ul.map-grid a").first.get_attribute("href")
                map_id = int(href.rstrip("/").split("/")[-1])
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
