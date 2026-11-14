"""Capture full-page screenshots of every demo page, for the design audit.

Usage:
    uv run python scripts/screenshots.py --out /tmp/shots/before \
        [--pages 'shops-*'] [--width 1920|1280|992|768|390|320 | --widths 1920,768 | --audit]
        [--keep-db]

`--audit` means widths 1920, 1280, 768 and 390 for every page (it ignores each page's
default widths). `--widths` takes a comma list. Without them the tool runs the default
widths (1280, 992, 768, 390, 320) and each page's own width list.

The tool builds a fresh SQLite database in a temp directory, runs `seed_demo`,
starts the dev server on a free port, signs in as each demo role and writes
`<out>/<page-name>@<width>.png`. At 390 px it prints `OVERFLOW <page>` for each
page that scrolls sideways. It prints `CLIPPED <page>` where a container cuts content
off. With `--audit` or `--widths` it makes the same checks at 768 px and prints
`OVERFLOW <page>@768` and `CLIPPED <page>@768`. It prints `FAIL <page> <status>` for a non-200 page
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
HEIGHTS = {1920: 1080, 1280: 800, 992: 800, 768: 1024, 390: 844, 320: 640}
DEFAULT_WIDTHS = (1280, 992, 768, 390, 320)
AUDIT_WIDTHS = (1920, 1280, 768, 390)
# Content that a container hides or scrolls inside itself. The page does not
# scroll sideways, but the content is still cut off.
CLIPPED_JS = """() => {
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg') || el.closest('.navbar')) continue;
    if (el.classList.contains('wm-skip-link')) continue;
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


def parse_widths(text: str) -> tuple[int, ...]:
    try:
        widths = tuple(int(w) for w in text.split(",") if w.strip())
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a comma list of widths: {text!r}") from None
    bad = [w for w in widths if w not in HEIGHTS]
    if not widths or bad:
        raise argparse.ArgumentTypeError(f"widths must come from {sorted(HEIGHTS)}; got {text!r}")
    return widths


def _act(page, action):
    if action == "menu_open":
        page.click(".navbar-toggler")
        page.wait_for_timeout(500)
        return
    from scripts.screenshot_pages import MODAL_SELECTORS

    if action == "sell_modal":
        # Fill the first visible sell form with its max quantity, then submit. A quantity
        # above the junk count opens the confirm modal. Never submit the confirm form.
        form = page.locator("form.wm-sell-form:visible").first
        qty = form.locator("input[type=number]").first
        qty.fill(qty.get_attribute("max") or "1")
        form.locator("[type=submit]").first.click()
    else:
        page.locator(f"{MODAL_SELECTORS[action]}:visible").first.click()
    page.wait_for_selector("#app-modal.show")
    page.wait_for_function(
        "document.querySelector('#app-modal .modal-content').children.length > 0"
    )
    page.wait_for_timeout(500)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--pages", default="*")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--width", type=int, choices=sorted(HEIGHTS))
    group.add_argument("--widths", type=parse_widths, help="comma list, e.g. 1920,768")
    group.add_argument("--audit", action="store_true", help="1920,1280,768,390 for every page")
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
    audit_mode = bool(args.audit or args.widths)
    if args.audit:
        widths = AUDIT_WIDTHS
    elif args.widths:
        widths = args.widths
    elif args.width:
        widths = (args.width,)
    else:
        widths = DEFAULT_WIDTHS
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
            for width in widths:
                contexts = {}
                for page_def in pages:
                    if audit_mode:
                        if page_def.audit_widths and width not in page_def.audit_widths:
                            continue
                    elif width not in page_def.widths:
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
                        # 390 prints as before. Audit runs also check 768, with a suffix.
                        if width == 390 or (audit_mode and width == 768):
                            tag = page_def.name + ("" if width == 390 else f"@{width}")
                            if page.evaluate(
                                "document.documentElement.scrollWidth"
                                " > document.documentElement.clientWidth"
                            ):
                                print(f"OVERFLOW {tag}")
                                overflow += 1
                            clipped = page.evaluate(CLIPPED_JS)
                            if clipped:
                                print(f"CLIPPED {tag} ({clipped})")
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
    used = f" at {','.join(map(str, widths))}" if audit_mode else ""
    print(
        f"Done: {taken} screenshots{used}, {overflow} OVERFLOW, {failed} failed. Output: {args.out}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
