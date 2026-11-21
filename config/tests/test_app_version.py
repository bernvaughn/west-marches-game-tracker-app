"""Tests for APP_VERSION loading, context processor, footer, deploy script, and .gitignore."""

import os
import subprocess
from pathlib import Path

import pytest
from django.test import RequestFactory, override_settings
from django.urls import reverse

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# Settings loader tests


def test_load_app_version_with_version_file(tmp_path):
    from config.settings import load_app_version

    version_file = tmp_path / "VERSION"
    version_file.write_text("v1.2.3\n", encoding="utf-8")
    assert load_app_version(base_dir=tmp_path) == "v1.2.3"


def test_load_app_version_no_file(tmp_path):
    from config.settings import load_app_version

    assert load_app_version(base_dir=tmp_path) == ""


def test_load_app_version_empty_file(tmp_path):
    from config.settings import load_app_version

    (tmp_path / "VERSION").write_text("", encoding="utf-8")
    assert load_app_version(base_dir=tmp_path) == ""


def test_load_app_version_whitespace_only(tmp_path):
    from config.settings import load_app_version

    (tmp_path / "VERSION").write_text("   \n\t\n  ", encoding="utf-8")
    assert load_app_version(base_dir=tmp_path) == ""


def test_load_app_version_env_wins_over_file(tmp_path):
    from config.settings import load_app_version

    (tmp_path / "VERSION").write_text("v1.0.0\n", encoding="utf-8")
    assert load_app_version(base_dir=tmp_path, environ={"DJANGO_APP_VERSION": "v2.0.0"}) == "v2.0.0"


def test_load_app_version_env_blank_falls_back_to_file(tmp_path):
    from config.settings import load_app_version

    (tmp_path / "VERSION").write_text("v1.0.0\n", encoding="utf-8")
    assert load_app_version(base_dir=tmp_path, environ={"DJANGO_APP_VERSION": ""}) == "v1.0.0"
    assert load_app_version(base_dir=tmp_path, environ={"DJANGO_APP_VERSION": "   "}) == "v1.0.0"


def test_load_app_version_first_line_only(tmp_path):
    from config.settings import load_app_version

    (tmp_path / "VERSION").write_text("v1.2.3\nv4.5.6\n", encoding="utf-8")
    assert load_app_version(base_dir=tmp_path) == "v1.2.3"


def test_load_app_version_directory_not_file(tmp_path):
    from config.settings import load_app_version

    (tmp_path / "VERSION").mkdir()
    assert load_app_version(base_dir=tmp_path) == ""


def test_load_app_version_undecodable_bytes(tmp_path):
    from config.settings import load_app_version

    (tmp_path / "VERSION").write_bytes(b"\xff\xfe")
    assert load_app_version(base_dir=tmp_path) == ""


# Context processor tests


def test_context_processor_returns_app_version(settings):
    from accounts.context_processors import app_name

    request = RequestFactory().get("/")
    with override_settings(APP_VERSION="v9.9.9"):
        ctx = app_name(request)
    assert ctx["APP_VERSION"] == "v9.9.9"


def test_context_processor_empty_when_not_set(settings):
    from accounts.context_processors import app_name

    request = RequestFactory().get("/")
    with override_settings(APP_VERSION=""):
        ctx = app_name(request)
    assert ctx["APP_VERSION"] == ""


# Footer tests


@pytest.mark.django_db
def test_footer_shows_version_for_anonymous_user(client, settings):
    settings.APP_VERSION = "v9.9.9"
    resp = client.get(reverse("about"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-site-footer-version" in html
    assert "v9.9.9" in html
    # Version should be inside the footer
    assert "<footer" in html
    footer_start = html.index("<footer")
    version_pos = html.index("v9.9.9")
    assert version_pos > footer_start


@pytest.mark.django_db
def test_footer_shows_version_for_signed_in_user(client, settings, player, login):
    settings.APP_VERSION = "v9.9.9"
    resp = login(player).get(reverse("about"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-site-footer-version" in html
    assert "v9.9.9" in html
    # Version should appear after "Suggest a feature"
    suggest_pos = html.index("Suggest a feature")
    version_pos = html.index("v9.9.9")
    assert version_pos > suggest_pos


@pytest.mark.django_db
def test_footer_no_version_element_when_empty(client, settings):
    settings.APP_VERSION = ""
    resp = client.get(reverse("about"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-site-footer-version" not in html


# .gitignore tests


def test_gitignore_has_version():
    gitignore = REPO_ROOT / ".gitignore"
    content = gitignore.read_text()
    # Should have /VERSION (root only) or VERSION
    lines = [
        line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")
    ]
    assert "/VERSION" in lines or "VERSION" in lines


# Deploy script tests


def test_deploy_script_writes_version_before_restart(tmp_path):
    """Full-run test: deploy script writes VERSION before restart call."""
    script_text = (REPO_ROOT / "deploy/deploy.sh").read_text()

    # Replace absolute constants with tmp paths
    app_dir = tmp_path / "app"
    lock_file = tmp_path / "deploy.lock"
    state_file = tmp_path / "last-deployed-tag"
    uv_path = tmp_path / "bin" / "uv"
    env_file = tmp_path / "downtime.env"

    app_dir.mkdir()
    (app_dir / ".git").mkdir()  # so no clone
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Create .venv/bin in app_dir for the relative python path
    venv_bin = app_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)

    # Create stubs that exit 0
    for name in ("git", "uv", "sudo", "curl", "flock", "systemctl", "journalctl", "python"):
        stub = bin_dir / name
        stub.write_text(
            '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "${CALLS_FILE}"\nexit 0\n',
        )
        stub.chmod(0o755)
        # Also put python in .venv/bin
        if name == "python":
            stub2 = venv_bin / name
            stub2.write_text(
                '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "${CALLS_FILE}"\nexit 0\n',
            )
            stub2.chmod(0o755)

    # curl stub prints ok for health check
    (bin_dir / "curl").write_text(
        '#!/usr/bin/env bash\necho "curl $*" >> "${CALLS_FILE}"\necho "ok"\nexit 0\n',
    )
    (bin_dir / "curl").chmod(0o755)

    # sudo stub snapshots VERSION at restart time
    snapshot_file = tmp_path / "version_at_restart.txt"
    sudo_script = (
        "#!/usr/bin/env bash\n"
        'echo "sudo $*" >> "${CALLS_FILE}"\n'
        'if [[ "$1" == "systemctl" && "$2" == "restart" ]]; then\n'
        f'  if [ -f "{app_dir}/VERSION" ]; then\n'
        f'    cat "{app_dir}/VERSION" > "{snapshot_file}"\n'
        "  else\n"
        f'    echo "MISSING" > "{snapshot_file}"\n'
        "  fi\n"
        "fi\n"
        "exit 0\n"
    )
    (bin_dir / "sudo").write_text(sudo_script)
    (bin_dir / "sudo").chmod(0o755)

    # backup.sh not executable -> backup step skipped
    # sleep not reached when curl returns ok

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["CALLS_FILE"] = str(tmp_path / "calls.txt")

    # Replace constants in script text
    replacements = {
        "APP_DIR=/srv/app": f"APP_DIR={app_dir}",
        "LOCK_FILE=/var/lib/downtime/deploy.lock": f"LOCK_FILE={lock_file}",
        "STATE_FILE=/var/lib/downtime/last-deployed-tag": f"STATE_FILE={state_file}",
        "UV=/home/deploy/.local/bin/uv": f"UV={uv_path}",
        "ENV_FILE=/etc/downtime.env": f"ENV_FILE={env_file}",
    }
    test_script = script_text
    for old, new in replacements.items():
        test_script = test_script.replace(old, new)

    # Run via stdin mode
    result = subprocess.run(
        ["bash", "-s", "--", "v1.2.3"],
        input=test_script,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    # Check VERSION file content
    version_file = app_dir / "VERSION"
    assert version_file.exists(), "VERSION file was not created"
    assert version_file.read_text() == "v1.2.3\n", f"VERSION content: {version_file.read_text()!r}"

    # Check snapshot at restart time
    assert snapshot_file.exists(), "snapshot not created"
    assert snapshot_file.read_text().strip() == "v1.2.3", f"snapshot: {snapshot_file.read_text()!r}"

    # Check call order: git checkout before sudo systemctl restart
    calls = (tmp_path / "calls.txt").read_text()
    # git is called as 'git -C ... checkout', find the checkout after fetch
    first_git_c = calls.index("git -C")
    checkout_idx = calls.index("checkout", first_git_c)
    restart_idx = calls.index("sudo systemctl restart")
    assert checkout_idx < restart_idx, "checkout not before restart"


def test_deploy_script_failed_run_writes_no_version(tmp_path):
    """Failed run (bad tag) writes no VERSION."""
    script_text = (REPO_ROOT / "deploy/deploy.sh").read_text()

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / ".git").mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Create .venv/bin in app_dir for the relative python path
    venv_bin = app_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)

    calls_file = tmp_path / "calls.txt"

    for name in ("git", "uv", "sudo", "curl", "flock", "systemctl", "journalctl", "python"):
        stub = bin_dir / name
        stub.write_text(
            '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "${CALLS_FILE}"\nexit 0\n',
        )
        stub.chmod(0o755)
        # Also put python in .venv/bin
        if name == "python":
            stub2 = venv_bin / name
            stub2.write_text(
                '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "${CALLS_FILE}"\nexit 0\n',
            )
            stub2.chmod(0o755)

    # git rev-parse exits 1 -> "Tag does not exist"
    git_script = (
        "#!/usr/bin/env bash\n"
        'for arg in "$@"; do\n'
        '  if [[ "$arg" == "rev-parse" ]]; then\n'
        "    exit 1\n"
        "  fi\n"
        "done\n"
        'echo "git $*" >> "${CALLS_FILE}"\n'
        "exit 0\n"
    )
    (bin_dir / "git").write_text(git_script)
    (bin_dir / "git").chmod(0o755)

    lock_file = tmp_path / "deploy.lock"
    state_file = tmp_path / "last-deployed-tag"
    uv_path = tmp_path / "bin" / "uv"
    env_file = tmp_path / "downtime.env"

    replacements = {
        "APP_DIR=/srv/app": f"APP_DIR={app_dir}",
        "LOCK_FILE=/var/lib/downtime/deploy.lock": f"LOCK_FILE={lock_file}",
        "STATE_FILE=/var/lib/downtime/last-deployed-tag": f"STATE_FILE={state_file}",
        "UV=/home/deploy/.local/bin/uv": f"UV={uv_path}",
        "ENV_FILE=/etc/downtime.env": f"ENV_FILE={env_file}",
    }
    test_script = script_text
    for old, new in replacements.items():
        test_script = test_script.replace(old, new)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["CALLS_FILE"] = str(calls_file)

    result = subprocess.run(
        ["bash", "-s", "--", "v1.2.3"],
        input=test_script,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Tag v1.2.3 does not exist" in result.stderr
    assert not (app_dir / "VERSION").exists(), "VERSION should not be created on failure"
