"""Shared browser environment setup for Playwright.

On the CodeHerder agent machine, Playwright's Chromium and its required libraries
are installed in shared, readable folders:
- /opt/playwright-browsers (contains chromium-1254 and chromium_headless_shell-1254)
- /opt/chrome-libs/root/usr/lib/x86_64-linux-gnu (extra shared libraries)

This module configures the environment to use those folders automatically when
they exist, without overriding values the user has already set.
"""

from __future__ import annotations

import os
from pathlib import Path

SHARED_BROWSERS_PATH = Path("/opt/playwright-browsers")
SHARED_CHROME_LIBS_PATH = Path("/opt/chrome-libs/root/usr/lib/x86_64-linux-gnu")


def use_shared_browser() -> None:
    """Configure Playwright to use the shared browser installation if available.

    - If /opt/playwright-browsers exists and PLAYWRIGHT_BROWSERS_PATH is not
      already set, set it to that path.
    - If /opt/chrome-libs/root/usr/lib/x86_64-linux-gnu exists and LD_LIBRARY_PATH
      is not already set, set it to that path.
    - Does nothing when the folders do not exist (so laptops and CI are unaffected).
    - Never overrides a value the person already set.
    """
    # Set PLAYWRIGHT_BROWSERS_PATH if not already set and shared folder exists
    if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
        if SHARED_BROWSERS_PATH.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(SHARED_BROWSERS_PATH)

    # Set LD_LIBRARY_PATH if not already set and shared folder exists
    if "LD_LIBRARY_PATH" not in os.environ:
        if SHARED_CHROME_LIBS_PATH.exists():
            os.environ["LD_LIBRARY_PATH"] = str(SHARED_CHROME_LIBS_PATH)


def check_browser(pw) -> None:
    """Verify that Playwright can launch Chromium.

    If the browser cannot be found, prints a clear one-line message with
    instructions and re-raises the original exception.

    Args:
        pw: A Playwright instance from `sync_playwright()`.

    Raises:
        The original exception from `pw.chromium.launch()`.
    """
    try:
        browser = pw.chromium.launch()
        browser.close()
    except Exception:
        # Print a clear one-line message, not a long stack trace
        shared_path = SHARED_BROWSERS_PATH
        msg = (
            f"Chromium not found. Run: PLAYWRIGHT_BROWSERS_PATH={shared_path} "
            f"uv run playwright install chromium (shared folder: {shared_path})"
        )
        print(msg)
        raise
