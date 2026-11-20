"""Tests for deploy configuration files: systemd unit, Caddyfile, env example."""

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"


def test_systemd_unit():
    """Test that downtime.service has all required keys and correct binding."""
    service_path = DEPLOY_DIR / "downtime.service"
    assert service_path.exists(), f"Missing {service_path}"

    content = service_path.read_text()

    # Required keys from spec
    required_keys = [
        "User=deploy",
        "Group=deploy",
        "WorkingDirectory=/srv/app",
        "EnvironmentFile=/etc/downtime.env",
        "ExecStart=/srv/app/.venv/bin/gunicorn config.wsgi:application"
        " --workers 2 --bind 127.0.0.1:8000 --timeout 30 --access-logfile -",
        "Restart=always",
        "RestartSec=2",
        "After=network.target",
        "WantedBy=multi-user.target",
        "NoNewPrivileges=yes",
        "PrivateTmp=yes",
        "ProtectSystem=strict",
        "ProtectHome=yes",
        "ReadWritePaths=/var/lib/downtime",
        "ProtectKernelTunables=yes",
        "ProtectControlGroups=yes",
    ]

    for key in required_keys:
        assert key in content, f"Missing required key: {key}"

    # Must bind to 127.0.0.1:8000
    assert "127.0.0.1:8000" in content, "Must bind to 127.0.0.1:8000"

    # Must NOT have 0.0.0.0 anywhere
    assert "0.0.0.0" not in content, "Must not bind to 0.0.0.0"

    # Verify sections exist
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "[Install]" in content


def test_caddyfile():
    """Test that Caddyfile has correct structure and no security headers."""
    caddy_path = DEPLOY_DIR / "Caddyfile"
    assert caddy_path.exists(), f"Missing {caddy_path}"

    content = caddy_path.read_text()

    # Strip comments for structural checks
    lines = content.splitlines()
    stripped = []
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            continue
        # Remove inline comments
        if "#" in line:
            line = line.split("#")[0].rstrip()
        if line:
            stripped.append(line)
    stripped_content = "\n".join(stripped)

    # Site address
    assert "app.downtimemarket.com" in stripped_content, "Missing site address"

    # encode zstd gzip
    assert "encode zstd gzip" in stripped_content, "Missing encode directive"

    # Static file handling with handle_path
    assert "handle_path /static/*" in stripped_content, "Missing handle_path /static/*"
    assert "root * /srv/app/staticfiles" in stripped_content, "Missing staticfiles root"
    assert 'header Cache-Control "public, max-age=31536000, immutable"' in stripped_content, (
        "Missing Cache-Control header"
    )
    assert "file_server" in stripped_content, "Missing file_server directive"

    # Reverse proxy to gunicorn
    assert "reverse_proxy 127.0.0.1:8000" in stripped_content, (
        "Missing reverse_proxy to 127.0.0.1:8000"
    )

    # Must NOT have security headers (Django sets them)
    forbidden_headers = [
        "Strict-Transport-Security",
        "X-Frame-Options",
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "Referrer-Policy",
    ]
    for header in forbidden_headers:
        assert header not in content, f"Caddyfile must not set {header} (Django handles it)"

    # Required comments
    assert "read access to /srv/app/staticfiles" in content, (
        "Missing permission comment for staticfiles"
    )
    assert "execute access on /srv/app" in content, "Missing permission comment for /srv/app"
    assert "caddy validate" in content, "Missing install comment with caddy validate"
    assert "systemctl reload caddy" in content, (
        "Missing install comment with systemctl reload caddy"
    )


def test_env_example():
    """Test that downtime.env.example has the five variables and no real secrets."""
    env_path = DEPLOY_DIR / "downtime.env.example"
    assert env_path.exists(), f"Missing {env_path}"

    content = env_path.read_text()

    # Parse non-comment KEY=VALUE lines
    vars_found = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            vars_found[key.strip()] = value.strip()

    # Exactly five required variables
    required_vars = {
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DATABASE_PATH",
        "RATELIMIT_TRUST_XFF",
        "TIME_ZONE",
    }
    assert set(vars_found.keys()) == required_vars, (
        f"Expected {required_vars}, got {set(vars_found.keys())}"
    )

    # Each variable appears in config/settings.py
    settings_path = REPO_ROOT / "config" / "settings.py"
    settings_text = settings_path.read_text()
    for var_name in required_vars:
        assert var_name in settings_text, f"{var_name} not read in config/settings.py"

    # No real secrets - values should be placeholders
    assert vars_found["DJANGO_SECRET_KEY"] == "replace-me-with-a-long-random-value", (
        "Secret key should be placeholder"
    )
    assert vars_found["DJANGO_ALLOWED_HOSTS"] == "app.downtimemarket.com", (
        "ALLOWED_HOSTS should be placeholder"
    )
    assert vars_found["DATABASE_PATH"] == "/var/lib/downtime/db.sqlite3", (
        "DATABASE_PATH should be placeholder"
    )
    assert vars_found["RATELIMIT_TRUST_XFF"] == "1", "RATELIMIT_TRUST_XFF should be placeholder"
    assert vars_found["TIME_ZONE"] == "UTC", "TIME_ZONE should be placeholder"

    # Commented key generator line
    assert "secrets.token_urlsafe(50)" in content, "Missing commented key generator line"


def test_manage_check_deploy():
    """Test that manage.py check --deploy exits 0 with env example values."""
    env_path = DEPLOY_DIR / "downtime.env.example"
    content = env_path.read_text()

    # Parse env vars (ignore comments)
    env = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()

    # Replace placeholder secret key with a random 50-char string with many unique chars
    import secrets

    env["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(50)[:50]

    # Use a temporary database path
    with tempfile.TemporaryDirectory() as tmpdir:
        env["DATABASE_PATH"] = str(Path(tmpdir) / "test.db")

        # Minimal clean environment
        test_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(Path.home()),
            "DJANGO_SETTINGS_MODULE": "config.settings",
            **env,
        }

        # Run manage.py check --deploy
        result = subprocess.run(
            [sys.executable, "manage.py", "check", "--deploy"],
            cwd=REPO_ROOT,
            env=test_env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    # Exit code must be 0
    assert result.returncode == 0, (
        f"check --deploy failed with code {result.returncode}:"
        f"\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    # No security.* warnings should appear
    security_warnings = [line for line in result.stderr.splitlines() if "security.W" in line]
    assert not security_warnings, "Security warnings found:\n" + "\n".join(security_warnings)

    # Print any other warnings for visibility in test output
    other_warnings = [
        line for line in result.stderr.splitlines() if "W" in line and "security.W" not in line
    ]
    if other_warnings:
        print("Non-security warnings (listed in PR):")
        for w in other_warnings:
            print(f"  {w}")


if __name__ == "__main__":
    # Allow running directly with pytest or python
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
