"""Browser-free tests for scripts/flow_check_lib.py.

These tests need no browser and run under the default pytest run.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from accounts.demo import DEMO_LOGINS  # noqa: E402
from scripts import flow_check_lib  # noqa: E402

REAL_DB = ROOT / "db.sqlite3"


def _real_db_mtime():
    try:
        return os.path.getmtime(REAL_DB)
    except FileNotFoundError:
        return None


class _FakeMessage:
    def __init__(self, type, text):
        self.type = type
        self.text = text


class _FakeResponse:
    def __init__(self, status, url):
        self.status = status
        self.url = url


class _FakePage:
    def __init__(self):
        self.handlers = {}

    def on(self, event, fn):
        self.handlers.setdefault(event, []).append(fn)


@pytest.mark.slow
def test_fresh_demo_db_creates_seeded_database(tmp_path):
    db_path = tmp_path / "demo.sqlite3"
    before = _real_db_mtime()
    env = flow_check_lib.fresh_demo_db(db_path)
    after = _real_db_mtime()

    # The real database is never touched.
    assert before == after
    # The returned env points at the temp file.
    assert env["DATABASE_PATH"] == str(db_path)
    assert env["DJANGO_SETTINGS_MODULE"] == "config.settings"
    assert env["DJANGO_DEBUG"] == "1"
    assert db_path.exists()

    con = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "django_migrations" in tables  # migrate ran
        assert "accounts_user" in tables
        assert "accounts_club" in tables
        assert con.execute("SELECT 1 FROM accounts_user WHERE email='alice@example.com'").fetchone()
        assert con.execute("SELECT 1 FROM accounts_club WHERE slug='demo'").fetchone()
    finally:
        con.close()


def test_fresh_demo_db_refuses_non_empty_file(tmp_path):
    db_path = tmp_path / "demo.sqlite3"
    db_path.write_bytes(b"not empty")
    with pytest.raises(FileExistsError):
        flow_check_lib.fresh_demo_db(db_path)


def test_role_emails_match_demo_logins():
    demo_emails = {email for email, _label in DEMO_LOGINS}
    assert set(flow_check_lib.ROLE_EMAILS.values()) <= demo_emails


def test_recorder_collects_problems():
    page = _FakePage()
    rec = flow_check_lib.Recorder()
    rec.attach(page)

    console_handler = page.handlers["console"][0]
    pageerror_handler = page.handlers["pageerror"][0]
    response_handler = page.handlers["response"][0]

    # Console error is collected.
    console_handler(_FakeMessage("error", "oops"))
    assert rec.console_errors == ["oops"]
    # Console warning is ignored.
    console_handler(_FakeMessage("warning", "noise"))
    assert rec.console_errors == ["oops"]
    # CSP message goes to both console errors and CSP violations.
    console_handler(_FakeMessage("error", "Content Security Policy: violated"))
    assert rec.console_errors == ["oops", "Content Security Policy: violated"]
    assert rec.csp_violations == ["Content Security Policy: violated"]
    # Page error is collected.
    pageerror_handler(RuntimeError("boom"))
    assert rec.page_errors == ["boom"]
    # 200 is ignored; 4xx/5xx are collected.
    response_handler(_FakeResponse(200, "http://x/ok"))
    response_handler(_FakeResponse(404, "http://x/missing"))
    response_handler(_FakeResponse(500, "http://x/broke"))
    assert rec.http_errors == ["404 http://x/missing", "500 http://x/broke"]
    # rec is not clean because it collected a console error above.

    # A fresh recorder starts clean; check() logs controls and flips clean.
    clean_rec = flow_check_lib.Recorder()
    clean_rec.check("f", "/u", "c1", "expected1")
    clean_rec.check("f", "/u", "c2", "expected2")
    clean_rec.check("f", "/u", "c3", "expected3")
    assert clean_rec.controls_tried == 3
    assert clean_rec.clean

    clean_rec.check("f", "/u", "bad", "x", ok=False)
    assert not clean_rec.clean
    problems = clean_rec.problems()
    assert any("bad" in p for p in problems)

    mark = clean_rec.mark()
    clean_rec.check("f", "/u", "c4", "x", ok=False)
    since = clean_rec.since(mark)
    assert len(since) == 1
    assert clean_rec.summary()["controls_tried"] == 5


def test_server_env_defaults_and_resend_key():
    base = {
        "DATABASE_PATH": "/tmp/x.sqlite3",
        "DJANGO_SETTINGS_MODULE": "config.settings",
    }
    env = flow_check_lib._server_env(base)
    assert env["DJANGO_SECURE_SSL_REDIRECT"] == "0"
    assert env["RATELIMIT_LOGIN_ATTEMPTS"] == "100000"
    assert env["RATELIMIT_MCP_ATTEMPTS"] == "100000"
    # Inherited RESEND_API_KEY is removed.
    assert "RESEND_API_KEY" not in env
    # Caller key is kept.
    base_with_key = dict(base)
    base_with_key["RESEND_API_KEY"] = "dummy"
    env_with_key = flow_check_lib._server_env(base_with_key)
    assert env_with_key["RESEND_API_KEY"] == "dummy"
    # Explicit caller values are not overridden by setdefault.
    base_debug = dict(base)
    base_debug["DJANGO_DEBUG"] = "0"
    assert flow_check_lib._server_env(base_debug)["DJANGO_DEBUG"] == "0"


def test_source_guard_no_wait_for_function_or_pkill():
    source = Path(flow_check_lib.__file__).read_text()
    assert "wait_for_function" not in source
    assert "pkill" not in source
