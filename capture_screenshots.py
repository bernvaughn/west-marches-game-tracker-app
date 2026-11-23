#!/usr/bin/env python
"""Capture screenshots of the reminder settings page."""

import os
import subprocess
import time
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def run_django_server():
    """Start Django test server in background."""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "config.test_settings"
    proc = subprocess.Popen(
        ["uv", "run", "python", "manage.py", "runserver", "8000"],
        env=env,
        cwd="/home/ch/sessions/01a1ff2f-62c3-7df4-843d-f78fc7e9c257/west-marches-game-tracker-app",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to start
    time.sleep(3)
    return proc


def capture_screenshots():
    """Capture screenshots using Playwright."""
    server_proc = run_django_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})

            # Navigate to login page
            page.goto("http://localhost:8000/login/")
            page.wait_for_load_state("networkidle")

            # Create test user and club via Django shell
            # We'll use the existing test setup approach
            page.fill('input[name="email"]', "admin@test.com")
            page.fill('input[name="password"]', "pass12345678")
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # The test database is separate, so we need to set up data differently
            # Let's use a different approach - run the test and capture during test
            print("Need to set up test data first")
            browser.close()
    finally:
        server_proc.terminate()
        server_proc.wait()


if __name__ == "__main__":
    capture_screenshots()