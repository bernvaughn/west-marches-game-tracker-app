"""Sweep every demo page for browser problems.

Usage:
    uv run python scripts/console_sweep.py [--pages 'shops-*'] [--width 1280]

The tool builds a fresh SQLite database, runs `seed_demo`, starts the dev server
and visits each page in `screenshot_pages.py` as its role. It also opens every
modal trigger (`[data-app-modal]`) on the page. It records console errors and
warnings (including `htmx:*`), uncaught page errors, failed requests, 4xx/5xx
responses and server-log errors. It prints one line per problem and exits 1
if it found any.

Browser setup (no root): see the wiki page `testing/browser-checks-without-root`.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.screenshots import _free_port, _wait_for  # noqa: E402

MAX_MODALS = 12
LOG_MARKERS = ("Traceback", "Internal Server Error", " ERROR ", "Not Found:", "Bad Request:")


def _login(browser, base, email, password, width):
    ctx = browser.new_context(viewport={"width": width, "height": 800})
    if email:
        pg = ctx.new_page()
        pg.goto(f"{base}/accounts/login/")
        pg.fill("input[name=username]", email)
        pg.fill("input[name=password]", password)
        pg.locator("form button[type=submit], form input[type=submit]").first.click()
        pg.wait_for_load_state("networkidle")
        pg.close()
    return ctx


def _watch(page, problems, label):
    def add(kind, text):
        problems.append(f"{label}: {kind}: {text}")

    page.on(
        "console",
        lambda m: (
            add("console." + m.type, f"{m.text} ({m.location.get('url', '')})")
            if m.type in ("error", "warning")
            else None
        ),
    )
    page.on("pageerror", lambda e: add("pageerror", str(e)))
    page.on("requestfailed", lambda r: add("request failed", f"{r.url} {r.failure}"))
    page.on("response", lambda r: add("http", f"{r.status} {r.url}") if r.status >= 400 else None)


def _wait_modal(page, problems, label, what) -> bool:
    """Wait for the shared modal to show content, then close it with Escape."""
    try:
        page.wait_for_selector("#app-modal.show", timeout=5000)
        page.wait_for_function(
            "document.querySelector('#app-modal .modal-content').children.length > 0",
            timeout=5000,
        )
    except Exception as exc:
        problems.append(f"{label}: {what} did not open: {type(exc).__name__}")
        return False
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return True


def _open_modals(page, base, path, problems, label):
    """Open each modal trigger on a freshly loaded page, then close it."""
    # One trigger per URL shape: `/shops/1/sell/5/` and `/shops/1/sell/6/` count as one.
    keys = page.eval_on_selector_all(
        "[data-app-modal]",
        "els => els.map(e => (e.getAttribute('hx-get') || e.getAttribute('href') || '')"
        ".replace(/[0-9]+/g, 'N'))",
    )
    first = {}
    for i, key in enumerate(keys):
        first.setdefault(key, i)
    opened = False
    for i in sorted(first.values())[:MAX_MODALS]:
        if opened:
            page.goto(base + path, wait_until="load")
        trigger = page.locator("[data-app-modal]").nth(i)
        if not trigger.is_visible():
            continue
        trigger.dispatch_event("click")  # SVG tiles can overlap, so a real click may miss
        opened = _wait_modal(page, problems, label, f"modal {i}") or opened
    # The sell confirm modal opens from a form post, not a [data-app-modal] link.
    # Submit the first sell form only; never submit the confirm form, so the seed stays put.
    if page.locator("form.wm-sell-form").count():
        if opened:
            page.goto(base + path, wait_until="load")
        page.locator("form.wm-sell-form [type=submit]").first.click()
        _wait_modal(page, problems, label, "sell confirm modal")


def sweep(pages_glob="*", width=1280) -> list[str]:
    """Return a list of problem strings. An empty list means a clean sweep."""
    tmp = Path(tempfile.mkdtemp(prefix="sweep-db-"))
    env = {
        **os.environ,
        "DATABASE_PATH": str(tmp / "db.sqlite3"),
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_DEBUG": "1",
    }
    for cmd in ("migrate", "seed_demo"):
        subprocess.run(
            [sys.executable, "manage.py", cmd],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    # Resolve every URL before Playwright starts: its event loop blocks ORM calls.
    resolve = subprocess.run(
        [
            sys.executable,
            "-c",
            "import django, json;django.setup();"
            "from accounts.demo import DEMO_PASSWORD;"
            "from scripts.screenshot_pages import PAGES, ROLES, demo_objects, extra_fixtures;"
            "extra_fixtures();d=demo_objects();"
            "print(json.dumps([{p.name:p.url(d) for p in PAGES}, ROLES, DEMO_PASSWORD]))",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    import json

    urls, ROLES, DEMO_PASSWORD = json.loads(resolve.stdout.strip().splitlines()[-1])
    from scripts.screenshot_pages import PAGES

    pages = [p for p in PAGES if fnmatch.fnmatch(p.name, pages_glob)]
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    log_path = tmp / "server.log"
    problems: list[str] = []
    with open(log_path, "w") as log:
        server = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", "--noreload", f"127.0.0.1:{port}"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for(f"{base}/accounts/login/", server)
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                contexts = {}
                for p in pages:
                    if p.role not in contexts:
                        contexts[p.role] = _login(
                            browser, base, ROLES[p.role], DEMO_PASSWORD, width
                        )
                    page = contexts[p.role].new_page()
                    label = f"{p.name} ({p.role})"
                    _watch(page, problems, label)
                    try:
                        resp = page.goto(base + urls[p.name], wait_until="networkidle")
                        if resp is None or resp.status != 200:
                            problems.append(f"{label}: status {resp.status if resp else None}")
                        else:
                            if p.action == "menu_open":
                                page.click(".navbar-toggler")
                                page.wait_for_timeout(300)
                            _open_modals(page, base, urls[p.name], problems, label)
                    except Exception as exc:
                        problems.append(f"{label}: {type(exc).__name__}: {exc}")
                    finally:
                        page.close()
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)
    for line in log_path.read_text().splitlines():
        if any(m in line for m in LOG_MARKERS):
            problems.append(f"server log: {line}")
    shutil.rmtree(tmp, ignore_errors=True)
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", default="*")
    ap.add_argument("--width", type=int, default=1280)
    args = ap.parse_args()
    problems = sweep(args.pages, args.width)
    for line in problems:
        print(line)
    print(f"Done: {len(problems)} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
