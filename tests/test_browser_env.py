"""Tests for the shared browser environment helper."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    """Ensure a clean environment for each test."""
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    # Clear module cache so browser_env re-reads environment
    for mod in list(sys.modules):
        if mod.startswith("browser_env"):
            del sys.modules[mod]
    yield


def _import_browser_env():
    """Import browser_env with scripts on sys.path."""
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    import browser_env

    return browser_env


def test_use_shared_browser_sets_vars_when_folders_exist(monkeypatch, tmp_path):
    """use_shared_browser sets PLAYWRIGHT_BROWSERS_PATH and LD_LIBRARY_PATH when folders exist."""
    browsers_dir = tmp_path / "playwright-browsers"
    libs_dir = tmp_path / "chrome-libs" / "root" / "usr" / "lib" / "x86_64-linux-gnu"
    browsers_dir.mkdir(parents=True)
    libs_dir.mkdir(parents=True)

    browser_env = _import_browser_env()

    with (
        patch.object(browser_env, "SHARED_BROWSERS_PATH", browsers_dir),
        patch.object(browser_env, "SHARED_CHROME_LIBS_PATH", libs_dir),
    ):
        browser_env.use_shared_browser()

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(browsers_dir)
    assert os.environ["LD_LIBRARY_PATH"] == str(libs_dir)


def test_use_shared_browser_never_overrides_existing_vars(monkeypatch, tmp_path):
    """use_shared_browser does not override vars that are already set."""
    browsers_dir = tmp_path / "playwright-browsers"
    libs_dir = tmp_path / "chrome-libs" / "root" / "usr" / "lib" / "x86_64-linux-gnu"
    browsers_dir.mkdir(parents=True)
    libs_dir.mkdir(parents=True)

    custom_browsers = "/custom/browsers"
    custom_libs = "/custom/libs:/other/libs"

    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", custom_browsers)
    monkeypatch.setenv("LD_LIBRARY_PATH", custom_libs)

    browser_env = _import_browser_env()

    with (
        patch.object(browser_env, "SHARED_BROWSERS_PATH", browsers_dir),
        patch.object(browser_env, "SHARED_CHROME_LIBS_PATH", libs_dir),
    ):
        browser_env.use_shared_browser()

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == custom_browsers
    assert os.environ["LD_LIBRARY_PATH"] == custom_libs


def test_use_shared_browser_keeps_existing_ld_library_path(monkeypatch, tmp_path):
    """use_shared_browser does not modify LD_LIBRARY_PATH if already set (never overrides)."""
    browsers_dir = tmp_path / "playwright-browsers"
    libs_dir = tmp_path / "chrome-libs" / "root" / "usr" / "lib" / "x86_64-linux-gnu"
    browsers_dir.mkdir(parents=True)
    libs_dir.mkdir(parents=True)

    existing_libs = "/existing/path:/another/path"
    monkeypatch.setenv("LD_LIBRARY_PATH", existing_libs)

    browser_env = _import_browser_env()

    with (
        patch.object(browser_env, "SHARED_BROWSERS_PATH", browsers_dir),
        patch.object(browser_env, "SHARED_CHROME_LIBS_PATH", libs_dir),
    ):
        browser_env.use_shared_browser()

    # Should keep existing LD_LIBRARY_PATH unchanged (never overrides)
    assert os.environ["LD_LIBRARY_PATH"] == existing_libs
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(browsers_dir)


def test_use_shared_browser_does_nothing_when_folders_missing(monkeypatch, tmp_path):
    """use_shared_browser does nothing when the shared folders do not exist."""
    # Point to non-existent paths
    missing_browsers = tmp_path / "does-not-exist"
    missing_libs = tmp_path / "also-missing"

    browser_env = _import_browser_env()

    with (
        patch.object(browser_env, "SHARED_BROWSERS_PATH", missing_browsers),
        patch.object(browser_env, "SHARED_CHROME_LIBS_PATH", missing_libs),
    ):
        browser_env.use_shared_browser()

    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ
    assert "LD_LIBRARY_PATH" not in os.environ


def test_use_shared_browser_only_browsers_exist(monkeypatch, tmp_path):
    """use_shared_browser sets only PLAYWRIGHT_BROWSERS_PATH when only browsers folder exists."""
    browsers_dir = tmp_path / "playwright-browsers"
    browsers_dir.mkdir(parents=True)
    missing_libs = tmp_path / "chrome-libs" / "root" / "usr" / "lib" / "x86_64-linux-gnu"

    browser_env = _import_browser_env()

    with (
        patch.object(browser_env, "SHARED_BROWSERS_PATH", browsers_dir),
        patch.object(browser_env, "SHARED_CHROME_LIBS_PATH", missing_libs),
    ):
        browser_env.use_shared_browser()

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(browsers_dir)
    assert "LD_LIBRARY_PATH" not in os.environ


def test_use_shared_browser_only_libs_exist(monkeypatch, tmp_path):
    """use_shared_browser sets only LD_LIBRARY_PATH when only libs folder exists."""
    missing_browsers = tmp_path / "playwright-browsers"
    libs_dir = tmp_path / "chrome-libs" / "root" / "usr" / "lib" / "x86_64-linux-gnu"
    libs_dir.mkdir(parents=True)

    browser_env = _import_browser_env()

    with (
        patch.object(browser_env, "SHARED_BROWSERS_PATH", missing_browsers),
        patch.object(browser_env, "SHARED_CHROME_LIBS_PATH", libs_dir),
    ):
        browser_env.use_shared_browser()

    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ
    assert os.environ["LD_LIBRARY_PATH"] == str(libs_dir)
