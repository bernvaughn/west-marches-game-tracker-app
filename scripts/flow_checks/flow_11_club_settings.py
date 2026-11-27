"""Flow 11: club admin settings - "Send test email" control.

Verifies the club settings page is honest when RESEND_API_KEY is unset:
MAIL_ENABLED is true only under DEBUG, so the page advertises email as on,
but a test email cannot be delivered. The page must show the "test email
unavailable" notice and disable the recipient select and Send button.

Run:
    uv run python scripts/flow_checks/flow_11_club_settings.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from scripts.flow_check_lib import (  # noqa: E402
    Recorder,
    fresh_demo_db,
    launch_browser,
    login,
    run_server,
)

FLOW = "flow 11"
CLUB_SLUG = "demo"
SETTINGS_PATH = f"/c/{CLUB_SLUG}/accounts/settings/"


def check_settings(page, base_url: str, rec: Recorder, width: int) -> None:
    """Log in as the club admin and verify the test email card state."""
    login(page, base_url, "gm")
    page.goto(f"{base_url}{SETTINGS_PATH}", wait_until="networkidle")

    notice = page.locator(".wm-alert--info, .alert-info").first
    notice_text = notice.text_content() if notice.is_visible() else ""
    rec.check(
        FLOW,
        page.url,
        f"test email unavailable notice @{width}",
        "visible",
        actual="visible" if notice.is_visible() else "hidden",
        ok=notice.is_visible(),
    )
    rec.check(
        FLOW,
        page.url,
        f"notice mentions missing key @{width}",
        "No RESEND_API_KEY is set",
        actual=notice_text,
        ok="No RESEND_API_KEY is set" in notice_text,
    )

    select = page.locator("#id_recipient")
    button = page.locator("button:has-text('Send test email')").first
    rec.check(
        FLOW,
        page.url,
        f"recipient select disabled @{width}",
        "disabled",
        actual="disabled" if select.is_disabled() else "enabled",
        ok=select.is_disabled(),
    )
    rec.check(
        FLOW,
        page.url,
        f"Send button disabled @{width}",
        "disabled",
        actual="disabled" if button.is_disabled() else "enabled",
        ok=button.is_disabled(),
    )

    # Email is on under DEBUG, so there must be no "Email is disabled" banner.
    body = page.content()
    rec.check(
        FLOW,
        page.url,
        f"no 'Email is disabled' banner @{width}",
        "absent",
        actual="present" if "Email is disabled" in body else "absent",
        ok="Email is disabled" not in body,
    )


def main() -> int:
    problems: list[str] = []
    browser_name = "unknown"
    with tempfile.TemporaryDirectory(prefix="flow-11-") as td:
        db_path = Path(td) / "demo.sqlite3"
        # DJANGO_DEBUG=1, RESEND_API_KEY unset: email on but cannot be sent.
        env = fresh_demo_db(db_path)
        with run_server(env) as server:
            with sync_playwright() as pw:
                browser, browser_name = launch_browser(pw)
                print(f"flow 11: browser={browser_name}")
                try:
                    for width in (1280, 390):
                        height = 844 if width == 390 else 800
                        ctx = browser.new_context(viewport={"width": width, "height": height})
                        page = ctx.new_page()
                        rec = Recorder()
                        rec.attach(page)
                        try:
                            check_settings(page, server.base_url, rec, width)
                            if not rec.clean:
                                problems.extend(rec.problems())
                        finally:
                            ctx.close()
                finally:
                    browser.close()
    if problems:
        print("flow 11: PROBLEMS")
        for p in problems:
            print(f"  {p}")
        return 1
    print(
        f"flow 11: clean recorder, browser={browser_name}, "
        "test email unavailable notice + disabled controls at 1280 and 390."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
