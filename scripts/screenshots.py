"""Capture full-page screenshots of every demo page, for the design audit.

Usage:
    uv run python scripts/screenshots.py --out /tmp/shots/before \
        [--pages 'shops-*'] [--width 1280|390] [--keep-db]

The tool builds a fresh SQLite database in a temp directory, runs `seed_demo`,
starts the dev server on a free port, signs in as each demo role and writes
`<out>/<page-name>@<width>.png`. At 390 px it prints `OVERFLOW <page>` for each
page that scrolls sideways. It prints `CLIPPED <page>` where a container cuts content
off. It prints `FAIL <page> <status>` for a non-200 page
and exits 1 if any page failed.

Browser setup (no root): see the wiki page `testing/browser-checks-without-root`.
Env vars: PLAYWRIGHT_BROWSERS_PATH (where Chromium lives) and LD_LIBRARY_PATH
(for libnspr4, libnss3 and libasound2 if the system lacks them).
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEIGHTS = {1280: 800, 390: 844}
# Content that a container hides or scrolls inside itself. The page does not
# scroll sideways, but the content is still cut off.
CLIPPED_JS = """() => {
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg') || el.closest('.navbar')) continue;
    const st = getComputedStyle(el);
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0 &&
        /(auto|scroll|hidden|clip)/.test(st.overflowX)) {
      const c = String(el.className).split(' ')[0];
      out.push(el.tagName.toLowerCase() + (c ? '.' + c : ''));
    }
  }
  return [...new Set(out)].slice(0, 4).join(', ');
}"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for(url: str, proc: subprocess.Popen, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            raise RuntimeError("Dev server exited early.")
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError("Dev server did not start.")


def _act(page, action):
    if action == "menu_open":
        page.click(".navbar-toggler")
        page.wait_for_timeout(500)
        return
    link = {
        "buy_modal": "a[data-app-modal]",
        "tile_modal": "svg a[data-app-modal]",
        "grant_modal": "a[data-app-modal]",
    }[action]
    if action == "tile_modal":
        # Prefer the tile that holds the Wolf Den.
        link = "svg a[data-app-modal]"
    page.locator(link).first.click()
    page.wait_for_selector("#app-modal.show")
    page.wait_for_function(
        "document.querySelector('#app-modal .modal-content').children.length > 0"
    )
    page.wait_for_timeout(500)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--pages", default="*")
    ap.add_argument("--width", type=int, choices=sorted(HEIGHTS))
    ap.add_argument("--keep-db", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="shots-db-"))
    env = {
        **os.environ,
        "DATABASE_PATH": str(tmp / "db.sqlite3"),
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_DEBUG": "1",
    }
    os.environ.update(env)
    sys.path.insert(0, str(ROOT))
    for cmd in ("migrate", "seed_demo"):
        subprocess.run(
            [sys.executable, "manage.py", cmd],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    import django

    django.setup()
    from accounts.demo import DEMO_PASSWORD
    from scripts.screenshot_pages import PAGES, ROLES, demo_objects, extra_fixtures

    extra_fixtures()
    demo = demo_objects()
    pages = [p for p in PAGES if fnmatch.fnmatch(p.name, args.pages)]
    if not pages:
        print(f"No page matches {args.pages!r}.")
        return 2
    resolved = {p.name: p.url(demo) for p in pages}

    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", "--noreload", f"127.0.0.1:{port}"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    failed = overflow = taken = 0
    try:
        _wait_for(f"{base}/accounts/login/", server)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as exc:
                print(
                    f"Chromium did not start: {exc}\n"
                    "See the wiki page testing/browser-checks-without-root."
                )
                return 3
            for width in (args.width,) if args.width else sorted(HEIGHTS, reverse=True):
                contexts = {}
                for page_def in pages:
                    if width not in page_def.widths:
                        continue
                    role = page_def.role
                    if role not in contexts:
                        ctx = browser.new_context(
                            viewport={"width": width, "height": HEIGHTS[width]}
                        )
                        if ROLES[role]:
                            pg = ctx.new_page()
                            pg.goto(f"{base}/accounts/login/")
                            pg.fill("input[name=username]", ROLES[role])
                            pg.fill("input[name=password]", DEMO_PASSWORD)
                            pg.locator(
                                "form button[type=submit], form input[type=submit]"
                            ).first.click()
                            pg.wait_for_load_state("networkidle")
                            pg.close()
                        contexts[role] = ctx
                    page = contexts[role].new_page()
                    try:
                        resp = page.goto(base + resolved[page_def.name], wait_until="networkidle")
                        if resp is None or resp.status != 200:
                            print(f"FAIL {page_def.name} {resp.status if resp else 'none'}")
                            failed += 1
                            continue
                        if page_def.action:
                            _act(page, page_def.action)
                        if width == 390 and page.evaluate(
                            "document.documentElement.scrollWidth"
                            " > document.documentElement.clientWidth"
                        ):
                            print(f"OVERFLOW {page_def.name}")
                            overflow += 1
                        if width == 390:
                            clipped = page.evaluate(CLIPPED_JS)
                            if clipped:
                                print(f"CLIPPED {page_def.name} ({clipped})")
                        page.screenshot(
                            path=str(args.out / f"{page_def.name}@{width}.png"), full_page=True
                        )
                        taken += 1
                    except Exception as exc:
                        print(f"FAIL {page_def.name} {type(exc).__name__}: {exc}")
                        failed += 1
                    finally:
                        page.close()
                for ctx in contexts.values():
                    ctx.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        if not args.keep_db:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"Done: {taken} screenshots, {overflow} OVERFLOW, {failed} failed. Output: {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
