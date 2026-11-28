"""Browser test: the GM top bar fits on one row with no sideways scroll at 1280 px.

Covers bug C3 (GM top bar overflows by 13 px at exactly 1280 px). The fix lets
the club/character name shrink first so the Approvals button and its caret stay
fully visible.

Run with: uv run pytest -m browser scripts/test_topbar_overflow.py
"""

import tempfile
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from scripts.flow_check_lib import fresh_demo_db, launch_browser, login, run_server

# Widths that must show no horizontal scroll on the top bar. The bug spans
# 1200-1299 px for the game master, so that band is included.
WIDTHS = (390, 768, 992, 1100, 1199, 1200, 1240, 1279, 1280, 1300, 1366, 1440)
HEIGHT = 800
SHOPS_URL = "/c/demo/shops/"


def _page_size(page):
    return page.evaluate(
        "({scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth})"
    )


def _approvals_right_edge(page):
    locator = page.locator(".approvals-menu").first
    if not locator.count():
        return None
    box = locator.bounding_box()
    if box is None:
        return None
    return box["x"] + box["width"]


@pytest.mark.browser
def test_topbar_fits_without_sideways_scroll():
    """No sideways scroll on the top bar at any tested width for any role.

    At 1280 px for the GM the Approvals button and its caret are fully visible
    (right edge within the viewport). Fails on main for GM at 1200, 1240 and
    1280 px.
    """
    with tempfile.TemporaryDirectory(prefix="topbar-overflow-") as td:
        db_path = Path(td) / "demo.sqlite3"
        env = fresh_demo_db(db_path)
        with run_server(env) as server:
            with sync_playwright() as pw:
                browser, _ = launch_browser(pw)
                try:
                    for role in ("gm", "player", "admin"):
                        context = browser.new_context(viewport={"width": 1280, "height": HEIGHT})
                        page = context.new_page()
                        try:
                            login(page, server.base_url, role)
                            for width in WIDTHS:
                                page.set_viewport_size({"width": width, "height": HEIGHT})
                                page.goto(
                                    f"{server.base_url}{SHOPS_URL}",
                                    wait_until="networkidle",
                                )
                                sizes = _page_size(page)
                                assert sizes["scrollWidth"] <= sizes["innerWidth"], (
                                    f"{role} @{width}px: scrollWidth "
                                    f"{sizes['scrollWidth']} > innerWidth "
                                    f"{sizes['innerWidth']}"
                                )
                                if role == "gm" and width == 1280:
                                    edge = _approvals_right_edge(page)
                                    assert edge is not None, "gm @1280: Approvals button not found"
                                    assert edge <= sizes["innerWidth"], (
                                        f"gm @1280: Approvals right edge {edge} > "
                                        f"innerWidth {sizes['innerWidth']}"
                                    )
                        finally:
                            context.close()
                finally:
                    browser.close()
