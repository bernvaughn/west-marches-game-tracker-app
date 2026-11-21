"""Scratch script to take attendance page screenshots at 1280 and 390px.

This script uses the same approach as scripts/screenshots.py but only for
the attendance pages. It creates a temp database, runs seed_demo, starts
the dev server, and captures screenshots.
"""

import os
import sys
import tempfile
import time
import urllib.request
import socket
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HEIGHTS = {1920: 1080, 1280: 800, 992: 800, 768: 1024, 390: 844, 320: 640}


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


def _login(page, base_url, email, password):
    page.goto(f"{base_url}/accounts/login/")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{base_url}/c/demo/**")


def _screenshot_page(page, url, out_path, widths):
    for width in widths:
        height = HEIGHTS[width]
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(500)
        page.goto(url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        out_file = out_path.parent / f"{out_path.stem}@{width}.png"
        page.screenshot(path=str(out_file), full_page=True)
        print(f"Saved {out_file}")


def main():
    out_dir = Path("/tmp/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Create temp directory for database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "db.sqlite3"
        
        # Environment for subprocesses
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{db_path}"
        env["DJANGO_SETTINGS_MODULE"] = "config.settings"
        env["DJANGO_DEBUG"] = "1"
        env["DJANGO_SECRET_KEY"] = "test-secret-key-for-testing-only"

        # Run migrations and seed_demo
        print("Running migrations...")
        subprocess.run(
            [sys.executable, "manage.py", "migrate", "--noinput"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            env=env,
        )

        print("Seeding demo data...")
        subprocess.run(
            [sys.executable, "manage.py", "seed_demo"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            env=env,
        )

        # Also run extra_fixtures
        subprocess.run(
            [sys.executable, "-c", "import django; django.setup(); import scripts.screenshot_pages; scripts.screenshot_pages.extra_fixtures()"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            env=env,
        )

        # Start dev server
        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        print(f"Starting dev server on {base_url}...")
        proc = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            _wait_for(base_url, proc)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()

                # Login as GM
                page = context.new_page()
                _login(page, base_url, "gm@example.com", "pass12345678")

                # Get session pk
                import django
                django.setup()
                from play_sessions.models import PlaySession
                session = PlaySession.objects.filter(club__slug="demo").first()
                if not session:
                    raise RuntimeError("No demo session found")

                # Attendance page
                attendance_url = f"{base_url}/c/demo/sessions/{session.pk}/attendance/"
                _screenshot_page(page, attendance_url, out_dir / "attendance", (1280, 390))

                # Session detail page (Who is coming section)
                detail_url = f"{base_url}/c/demo/sessions/{session.pk}/"
                _screenshot_page(page, detail_url, out_dir / "who_is_coming", (1280, 390))

                browser.close()

        finally:
            proc.terminate()
            proc.wait(timeout=5)

    print("Done!")


if __name__ == "__main__":
    main()