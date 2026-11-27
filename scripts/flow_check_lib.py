"""Shared harness for the flow-check scripts.

Provides a fresh seeded demo database, a throwaway dev server, a browser,
role logins and a console/page/HTTP error recorder. Nothing here weakens the
CSP and nothing edits scripts/flow_check.py or .github/workflows.

Page waits poll ``page.evaluate`` from Python; Playwright's
wait-for-function helper is deliberately not used (the CSP has no
unsafe-eval).
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.browser_env import use_shared_browser  # noqa: E402
from scripts.screenshots import _free_port, _wait_for  # noqa: E402

DEMO_PASSWORD = "demo-password"
ROLE_EMAILS = {
    "admin": "admin@example.com",
    "gm": "gm@example.com",
    "player": "alice@example.com",
    "player2": "bob@example.com",
}

SWEEP_DEFAULTS = {
    "DJANGO_SECURE_SSL_REDIRECT": "0",
    "RATELIMIT_LOGIN_ATTEMPTS": "100000",
    "RATELIMIT_PASSWORD_ATTEMPTS": "100000",
    "RATELIMIT_OAUTH_TOKEN_ATTEMPTS": "100000",
    "RATELIMIT_MCP_ATTEMPTS": "100000",
}


def _base_env() -> dict:
    """Process env without an inherited RESEND_API_KEY.

    The throwaway server must not send real mail. A caller that wants the key
    (for example the club-admin email flow) adds it to the dict returned by
    :func:`fresh_demo_db`; :func:`run_server` keeps it.
    """
    env = dict(os.environ)
    env.pop("RESEND_API_KEY", None)
    return env


def fresh_demo_db(path: str | Path) -> dict:
    """Build a fresh seeded SQLite database at ``path``.

    Returns the env dict (with DATABASE_PATH set) for :func:`run_server`.
    Raises FileExistsError if ``path`` already exists and is non-empty, so the
    real database can never be overwritten.
    """
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        raise FileExistsError(f"refusing to overwrite non-empty database file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    env = _base_env()
    env["DATABASE_PATH"] = str(path)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings"
    env["DJANGO_DEBUG"] = "1"
    for cmd in ("migrate", "seed_demo"):
        subprocess.run(
            [sys.executable, "manage.py", cmd],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return env


def _server_env(env: dict) -> dict:
    """Build the server process env from ``env`` plus the throwaway defaults.

    ``env`` is kept as given, so a caller-set RESEND_API_KEY survives.
    """
    server_env = dict(env)
    for key, value in SWEEP_DEFAULTS.items():
        server_env.setdefault(key, value)
    return server_env


@dataclass
class Server:
    base_url: str
    pid: int
    log_path: Path


@contextlib.contextmanager
def run_server(env: dict, port: int | None = None):
    """Start ``manage.py runserver --noreload`` on a free port.

    Yields a :class:`Server`. Stops the server by PID in ``finally`` (terminate,
    then kill after a 10s grace period); it never falls back to killing by
    process name.
    """
    server_env = _server_env(env)
    port = port or _free_port()
    base_url = f"http://127.0.0.1:{port}"
    log_dir = Path(tempfile.mkdtemp(prefix="flow-check-server-"))
    log_path = log_dir / "server.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", "--noreload", f"127.0.0.1:{port}"],
        cwd=ROOT,
        env=server_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for(f"{base_url}/accounts/login/", proc)
        yield Server(base_url=base_url, pid=proc.pid, log_path=log_path)
    finally:
        log_file.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def launch_browser(pw):
    """Launch a browser via Playwright.

    Calls ``use_shared_browser()``, tries Firefox and falls back to Chromium.
    Returns ``(browser, name)`` where name is "firefox" or "chromium".
    """
    use_shared_browser()
    try:
        browser = pw.firefox.launch()
        return browser, "firefox"
    except Exception:
        browser = pw.chromium.launch()
        return browser, "chromium"


def login(page, base_url: str, role: str) -> None:
    """Log in as a demo role and wait until the browser leaves the login page."""
    email = ROLE_EMAILS.get(role, role)
    page.goto(f"{base_url}/accounts/login/", wait_until="networkidle")
    page.fill("input[name=username]", email)
    page.fill("input[name=password]", DEMO_PASSWORD)
    page.locator("form button[type=submit]").first.click()
    try:
        poll(page, "window.location.pathname !== '/accounts/login/'", timeout=15)
    except TimeoutError as exc:
        error_text = ""
        try:
            error_text = page.locator(
                ".alert-danger, [role=alert], .is-invalid"
            ).first.text_content()
        except Exception:
            pass
        raise AssertionError(
            f"login as {role!r} ({email}) stayed on /accounts/login/: {error_text}"
        ) from exc


def poll(page, expression: str, timeout: float = 10, interval: float = 0.1):
    """Poll ``page.evaluate(expression)`` until it returns a truthy value.

    Returns the first truthy value, otherwise raises TimeoutError.
    """
    end = time.time() + float(timeout)
    while time.time() < end:
        try:
            value = page.evaluate(expression)
        except Exception:
            value = None
        if value:
            return value
        time.sleep(float(interval))
    raise TimeoutError(f"poll timed out after {timeout}s: {expression}")


def wait_idle(page) -> None:
    page.wait_for_load_state("networkidle")


class Recorder:
    """Collect console errors, page errors, CSP violations and 4xx/5xx responses.

    Tracks every control logged with :meth:`check` and exposes a controls-tried
    count plus a clean/problem summary.
    """

    def __init__(self, page=None) -> None:
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self.csp_violations: list[str] = []
        self.http_errors: list[str] = []
        self.controls: list[dict] = []
        self._problems: list[str] = []
        if page is not None:
            self.attach(page)

    def attach(self, page) -> None:
        def on_console(msg) -> None:
            text = msg.text
            if msg.type == "error":
                self.console_errors.append(text)
                self._problem(f"console error: {text}")
            if "Content Security Policy" in text or "violates the following" in text:
                self.csp_violations.append(text)
                if msg.type != "error":
                    self._problem(f"csp violation: {text}")

        page.on("console", on_console)

        def on_pageerror(exc) -> None:
            text = str(exc)
            self.page_errors.append(text)
            self._problem(f"page error: {text}")

        page.on("pageerror", on_pageerror)

        def on_response(response) -> None:
            if response.status >= 400:
                text = f"{response.status} {response.url}"
                self.http_errors.append(text)
                self._problem(f"http {text}")

        page.on("response", on_response)

    def _problem(self, text: str) -> None:
        self._problems.append(text)

    def check(self, flow, url, control, expected, actual=None, ok=True):
        """Log one control result and print a ✓/✗ line."""
        record = {
            "flow": flow,
            "url": url,
            "control": control,
            "expected": expected,
            "actual": actual,
            "ok": ok,
        }
        self.controls.append(record)
        if not ok:
            self._problem(f"check failed [{flow}] {control}: expected {expected!r}, got {actual!r}")
        mark = "✓" if ok else "✗"
        print(f"{mark} {control}: {actual} (expected {expected})")

    @property
    def controls_tried(self) -> int:
        return len(self.controls)

    def problems(self) -> list[str]:
        return list(self._problems)

    @property
    def clean(self) -> bool:
        return not self._problems

    def mark(self) -> int:
        return len(self._problems)

    def since(self, mark: int) -> list[str]:
        return self._problems[mark:]

    def summary(self) -> dict:
        return {
            "flows": sorted({c["flow"] for c in self.controls}),
            "controls_tried": self.controls_tried,
            "problems": self.problems(),
        }


def main() -> int:
    """Smoke run: fresh DB, server, browser, each demo role opens /c/demo/."""
    problems: list[str] = []
    controls = 0
    browser_name = "unknown"
    with tempfile.TemporaryDirectory(prefix="flow-check-smoke-") as td:
        db_path = Path(td) / "demo.sqlite3"
        env = fresh_demo_db(db_path)
        with run_server(env) as server:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser, browser_name = launch_browser(pw)
                print(f"flow_check_lib smoke: browser={browser_name}")
                try:
                    for role in ROLE_EMAILS:
                        for width in (1280, 390):
                            height = 844 if width == 390 else 800
                            ctx = browser.new_context(viewport={"width": width, "height": height})
                            page = ctx.new_page()
                            rec = Recorder()
                            rec.attach(page)
                            try:
                                login(page, server.base_url, role)
                                resp = page.goto(
                                    f"{server.base_url}/c/demo/",
                                    wait_until="networkidle",
                                )
                                ok = resp is not None and resp.status == 200
                                rec.check(
                                    "smoke",
                                    f"{server.base_url}/c/demo/",
                                    f"club home as {role} @{width}",
                                    "200",
                                    actual=(resp.status if resp else None),
                                    ok=ok,
                                )
                                controls += rec.controls_tried
                                if not rec.clean:
                                    problems.append(
                                        f"{role} @{width}: recorder not clean: {rec.problems()}"
                                    )
                            finally:
                                ctx.close()
                finally:
                    browser.close()
    if problems:
        print("flow_check_lib smoke: PROBLEMS")
        for p in problems:
            print(f"  {p}")
        print(f"Done: {len(problems)} problem(s).")
        return 1
    print(
        f"flow_check_lib smoke: clean recorder, {controls} control(s) tried, "
        f"browser={browser_name}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
