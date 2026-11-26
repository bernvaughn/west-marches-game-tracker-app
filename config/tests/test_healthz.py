"""Tests for the /healthz endpoint."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

RATELIMIT_CACHE_SETTINGS = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "healthz-rate-limit-tests",
    }
}

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@pytest.mark.django_db
class TestHealthz:
    """Tests for the healthz view."""

    def test_anonymous_get_returns_ok(self, client):
        """Anonymous GET /healthz returns 200 with body 'ok'."""
        response = client.get("/healthz")

        assert response.status_code == 200
        assert response.get("Content-Type") == "text/plain"
        assert response.content.decode() == "ok"
        assert response["Cache-Control"] == "no-store"
        assert "Set-Cookie" not in response
        assert response.cookies == {}

    def test_head_returns_ok_with_empty_body(self, client):
        """HEAD /healthz returns 200 with an empty body."""
        response = client.head("/healthz")

        assert response.status_code == 200
        assert response.content == b""
        assert response["Cache-Control"] == "no-store"
        assert "Set-Cookie" not in response

    def test_reverse_healthz(self):
        """reverse('healthz') resolves to /healthz with no trailing slash."""
        assert reverse("healthz") == "/healthz"

    def test_post_returns_405(self, client):
        """POST /healthz returns 405 because only GET and HEAD are allowed."""
        response = client.post("/healthz")

        assert response.status_code == 405
        assert response["Cache-Control"] == "no-store"
        assert "Set-Cookie" not in response

    def test_put_and_delete_return_405(self, client):
        """PUT and DELETE /healthz return 405."""
        for method in ("put", "delete"):
            response = getattr(client, method)("/healthz")
            assert response.status_code == 405, method
            assert response["Cache-Control"] == "no-store"

    @override_settings(
        CACHES=RATELIMIT_CACHE_SETTINGS,
        RATELIMIT_HEALTHZ_ATTEMPTS=3,
        RATELIMIT_HEALTHZ_WINDOW=60,
    )
    def test_healthz_rate_limit_allows_under_limit(self, client):
        """Requests under the limit succeed with 200."""
        cache.clear()
        for _ in range(3):
            response = client.get("/healthz", REMOTE_ADDR="10.0.0.1")
            assert response.status_code == 200, response.status_code

    @override_settings(
        CACHES=RATELIMIT_CACHE_SETTINGS,
        RATELIMIT_HEALTHZ_ATTEMPTS=3,
        RATELIMIT_HEALTHZ_WINDOW=60,
    )
    def test_healthz_rate_limit_returns_429_over_limit(self, client):
        """Requests over the limit return 429 with a Retry-After header."""
        cache.clear()
        for _ in range(3):
            client.get("/healthz", REMOTE_ADDR="10.0.0.1")
        response = client.get("/healthz", REMOTE_ADDR="10.0.0.1")

        assert response.status_code == 429
        assert response.get("Retry-After")

    @override_settings(
        CACHES=RATELIMIT_CACHE_SETTINGS,
        RATELIMIT_HEALTHZ_ATTEMPTS=3,
        RATELIMIT_HEALTHZ_WINDOW=60,
    )
    def test_healthz_rate_limit_is_per_client_ip(self, client):
        """One IP hitting the limit does not limit another IP."""
        cache.clear()
        for _ in range(3):
            client.get("/healthz", REMOTE_ADDR="10.0.0.1")

        limited = client.get("/healthz", REMOTE_ADDR="10.0.0.1")
        assert limited.status_code == 429

        other = client.get("/healthz", REMOTE_ADDR="10.0.0.2")
        assert other.status_code == 200

    def test_database_error_returns_503_without_secret_text(self, client):
        """A failing database check returns 503 'database unavailable' only."""
        with mock.patch("config.views.connections") as mock_connections:
            mock_connections.__getitem__.side_effect = RuntimeError("secret-internal-detail")
            response = client.get("/healthz")

        assert response.status_code == 503
        assert response.get("Content-Type") == "text/plain"
        assert response.content.decode() == "database unavailable"
        assert "secret-internal-detail" not in response.content.decode()
        assert response["Cache-Control"] == "no-store"
        assert "Set-Cookie" not in response
        assert response.cookies == {}

    @pytest.mark.skipif(
        importlib.util.find_spec("gunicorn") is None,
        reason="gunicorn is not installed",
    )
    def test_gunicorn_check_config_exits_zero(self):
        """`python -m gunicorn --check-config config.wsgi` exits 0."""
        env = os.environ.copy()
        env["DJANGO_SECRET_KEY"] = "test-secret-key-for-gunicorn-check"

        result = subprocess.run(
            [sys.executable, "-m", "gunicorn", "--check-config", "config.wsgi"],
            cwd=BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
