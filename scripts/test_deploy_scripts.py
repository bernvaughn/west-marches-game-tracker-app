"""Tests for deploy/deploy.sh and deploy/backup.sh.

The backup tests need the `sqlite3` CLI; the shellcheck test needs the
`shellcheck` CLI. Both are skipped when the tool is missing.
"""

import os
import shutil
import sqlite3
import stat
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"
BACKUP_SCRIPT = DEPLOY_DIR / "backup.sh"
DEPLOY_SCRIPT = DEPLOY_DIR / "deploy.sh"

HAS_SQLITE3 = shutil.which("sqlite3") is not None
HAS_SHELLCHECK = shutil.which("shellcheck") is not None


def test_bash_n_passes_for_both_scripts():
    for script in (BACKUP_SCRIPT, DEPLOY_SCRIPT):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not HAS_SHELLCHECK, reason="shellcheck is not installed")
def test_shellcheck_passes_for_both_scripts():
    for script in (BACKUP_SCRIPT, DEPLOY_SCRIPT):
        result = subprocess.run(["shellcheck", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def make_db(path, rows):
    """Create a SQLite file with a `widgets` table holding the given rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE widgets (name TEXT, value INTEGER)")
        con.executemany("INSERT INTO widgets VALUES (?, ?)", rows)
        con.commit()
    finally:
        con.close()


def read_rows(path):
    con = sqlite3.connect(path)
    try:
        return con.execute("SELECT name, value FROM widgets ORDER BY name").fetchall()
    finally:
        con.close()


def run_backup(db_path, backup_dir, extra_env=None):
    env = dict(os.environ)
    env["DB_PATH"] = str(db_path)
    env["BACKUP_DIR"] = str(backup_dir)
    env["KEEP_DAYS"] = "14"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(BACKUP_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(not HAS_SQLITE3, reason="sqlite3 CLI is not installed")
def test_backup_creates_mode_600_copy_with_same_rows(tmp_path):
    db = tmp_path / "db.sqlite3"
    backup_dir = tmp_path / "backups"
    rows = [("alpha", 1), ("beta", 2), ("gamma", 3)]
    make_db(db, rows)

    result = run_backup(db, backup_dir)
    assert result.returncode == 0, result.stderr

    backups = [
        p for p in backup_dir.iterdir() if p.name.startswith("db-") and p.name.endswith(".sqlite3")
    ]
    assert len(backups) == 1, backups
    backup = backups[0]
    mode = stat.S_IMODE(backup.stat().st_mode)
    assert mode == 0o600, oct(mode)
    assert read_rows(backup) == rows
    assert backup.name in result.stdout
    # no temp leftovers: exactly one entry in the backup dir
    assert [p.name for p in backup_dir.iterdir()] == [backup.name]


@pytest.mark.skipif(not HAS_SQLITE3, reason="sqlite3 CLI is not installed")
def test_missing_database_exits_zero_and_creates_nothing(tmp_path):
    db = tmp_path / "missing.sqlite3"
    backup_dir = tmp_path / "backups"
    result = run_backup(db, backup_dir)
    assert result.returncode == 0, result.stderr
    assert "no database yet, nothing to back up" in result.stdout
    assert not backup_dir.exists() or not any(backup_dir.iterdir())


@pytest.mark.skipif(not HAS_SQLITE3, reason="sqlite3 CLI is not installed")
def test_corrupt_database_fails_and_leaves_no_backup(tmp_path):
    db = tmp_path / "db.sqlite3"
    db.write_bytes(os.urandom(4096))
    backup_dir = tmp_path / "backups"
    result = run_backup(db, backup_dir)
    assert result.returncode != 0
    backups = [
        p for p in backup_dir.iterdir() if p.name.startswith("db-") and p.name.endswith(".sqlite3")
    ]
    assert backups == [], backups
    temps = [p for p in backup_dir.iterdir() if p.name.startswith(".db-tmp")]
    assert temps == [], temps


@pytest.mark.skipif(not HAS_SQLITE3, reason="sqlite3 CLI is not installed")
def test_backup_prunes_old_files_and_keeps_notes(tmp_path):
    db = tmp_path / "db.sqlite3"
    make_db(db, [("keep", 9)])
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    old_time = time.time() - 20 * 86400

    old_backup = backup_dir / "db-20200101T000000Z.sqlite3"
    old_backup.write_text("old")
    os.utime(old_backup, (old_time, old_time))

    fresh_backup = backup_dir / "db-20260101T000000Z.sqlite3"
    fresh_backup.write_text("fresh")

    notes = backup_dir / "notes.txt"
    notes.write_text("notes")
    os.utime(notes, (old_time, old_time))

    nonmatching = backup_dir / "db-20200101T000000Z.txt"
    nonmatching.write_text("nonmatching")
    os.utime(nonmatching, (old_time, old_time))

    result = run_backup(db, backup_dir)
    assert result.returncode == 0, result.stderr

    names = {p.name for p in backup_dir.iterdir()}
    assert "db-20200101T000000Z.sqlite3" not in names, names
    assert "notes.txt" in names
    assert "db-20200101T000000Z.txt" in names
    assert "db-20260101T000000Z.sqlite3" in names
    new_backups = [
        p
        for p in backup_dir.iterdir()
        if p.name.startswith("db-")
        and p.name.endswith(".sqlite3")
        and p.name not in ("db-20200101T000000Z.sqlite3", "db-20260101T000000Z.sqlite3")
    ]
    assert len(new_backups) == 1


def make_stub_bin(tmp_path):
    """A fake PATH whose git/uv/sudo/etc. stubs record their calls."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls_file = tmp_path / "calls.txt"
    for name in ("git", "uv", "sudo", "curl", "flock", "systemctl", "journalctl"):
        stub = bin_dir / name
        stub.write_text(
            '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "${CALLS_FILE}"\nexit 0\n',
        )
        stub.chmod(0o755)
    return bin_dir, calls_file


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["main"],
        ["v1; rm -rf /"],
        ["V1"],
        ["v"],
        ["v1 2"],
        ["v1a; rm -rf /"],
        ["v10 x"],
        ["v1.2$(id)"],
        ["v1.2`id`"],
        ["v1\n"],
        [""],
    ],
)
def test_bad_or_missing_tag_does_nothing(tmp_path, args):
    bin_dir, calls_file = make_stub_bin(tmp_path)
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["CALLS_FILE"] = str(calls_file)

    result = subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    assert not calls_file.exists() or calls_file.read_text() == "", calls_file.read_text()
    assert "tag" in result.stderr.lower() or "usage" in result.stderr.lower()


@pytest.mark.parametrize("tag", ["v1", "v0.1.0", "v2.0.0-rc_1", "v10A"])
def test_valid_tag_passes_validation(tmp_path, tag):
    """A valid tag gets past validation and stops at the lock, not exit 2."""
    bin_dir, calls_file = make_stub_bin(tmp_path)
    # Make the lock fail so the run stops there and never reaches git. If the
    # real lock dir is missing, opening the lock file fails first; also exit 1.
    (bin_dir / "flock").write_text(
        '#!/usr/bin/env bash\necho "flock $*" >> "${CALLS_FILE}"\nexit 1\n',
    )
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["CALLS_FILE"] = str(calls_file)

    result = subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), tag],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (result.returncode, result.stderr)
    assert "invalid tag" not in result.stderr
    assert "missing tag" not in result.stderr
    calls = calls_file.read_text() if calls_file.exists() else ""
    assert "git" not in calls, calls


def test_bad_tag_via_stdin_does_nothing(tmp_path):
    bin_dir, calls_file = make_stub_bin(tmp_path)
    script_text = DEPLOY_SCRIPT.read_text()
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["CALLS_FILE"] = str(calls_file)

    result = subprocess.run(
        ["bash", "-s", "--", "main"],
        input=script_text,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    assert not calls_file.exists() or calls_file.read_text() == "", calls_file.read_text()


def test_deploy_script_contains_constants_and_failure_message():
    text = DEPLOY_SCRIPT.read_text()
    for constant in (
        "APP_DIR=",
        "REPO_URL=",
        "ENV_FILE=",
        "STATE_FILE=",
        "HEALTH_HOST=",
        "UV=",
        "LOCK_FILE=",
    ):
        assert constant in text, constant
    assert "Deploy of $TAG failed. Previous tag:" in text
    # flock is set up before git clone.
    assert text.index("flock") < text.index("git clone")
