"""Tests for redirect URI validation."""

import pytest
from django.test import override_settings

from agent_access.oauth.forms import validate_redirect_uris


class TestRedirectURIValidation:
    """Tests for redirect URI validation in production mode (DEBUG=False)."""

    @pytest.fixture(autouse=True)
    def _override_settings(self):
        """Override OAuth2 settings for production mode."""
        with override_settings(
            DEBUG=False,
            OAUTH2_PROVIDER={
                "ALLOW_URI_WILDCARDS": False,
                "ALLOW_LOCALHOST_LOOPBACK": False,
                "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
            },
        ):
            yield

    def test_https_redirect_uri_allowed_in_production(self):
        """HTTPS redirect URIs are allowed in production."""
        errors = validate_redirect_uris(["https://example.com/callback"])
        assert not errors, f"Expected no errors, got: {errors}"

    def test_http_redirect_uri_rejected_in_production(self):
        """HTTP redirect URIs are rejected in production."""
        errors = validate_redirect_uris(["http://example.com/callback"])
        assert errors
        assert "not allowed" in errors[0].lower()

    def test_localhost_rejected_in_production(self):
        """localhost redirect URIs are rejected in production."""
        errors = validate_redirect_uris(["http://localhost:6274/callback"])
        assert errors
        assert "localhost" in errors[0].lower()

    def test_loopback_ip_rejected_in_production(self):
        """Loopback IP (127.0.0.1) redirect URIs are rejected when
        ALLOW_LOCALHOST_LOOPBACK=False."""
        errors = validate_redirect_uris(["http://127.0.0.1:6274/callback"])
        assert errors

    def test_loopback_ip_https_rejected(self):
        """Loopback IP with HTTPS is rejected (RFC 8252 requires HTTP for loopback)."""
        errors = validate_redirect_uris(["https://127.0.0.1:6274/callback"])
        assert errors
        assert "http" in errors[0].lower()

    def test_fragment_rejected(self):
        """Redirect URIs with fragments are rejected."""
        errors = validate_redirect_uris(["https://example.com/callback#fragment"])
        assert errors
        assert "fragment" in errors[0].lower()

    def test_userinfo_rejected(self):
        """Redirect URIs with userinfo are rejected."""
        errors = validate_redirect_uris(["https://user:pass@example.com/callback"])
        assert errors
        assert "userinfo" in errors[0].lower() or "credentials" in errors[0].lower()

    def test_empty_redirect_uris_rejected(self):
        """Empty redirect_uris list is rejected."""
        errors = validate_redirect_uris([])
        assert errors
        assert "required" in errors[0].lower()


class TestRedirectURIValidationDevelopment:
    """Tests for redirect URI validation in development mode (DEBUG=True)."""

    @pytest.fixture(autouse=True)
    def _override_settings(self):
        """Override OAuth2 settings for development mode."""
        with override_settings(
            DEBUG=True,
            OAUTH2_PROVIDER={
                "ALLOW_URI_WILDCARDS": False,
                "ALLOW_LOCALHOST_LOOPBACK": True,
                "ALLOWED_REDIRECT_URI_SCHEMES": ["http", "https"],
            },
        ):
            yield

    def test_http_redirect_uri_allowed_in_development(self):
        """HTTP redirect URIs are allowed in development."""
        errors = validate_redirect_uris(["http://example.com/callback"])
        assert not errors, f"Expected no errors, got: {errors}"

    def test_localhost_allowed_in_development(self):
        """localhost redirect URIs are allowed in development."""
        errors = validate_redirect_uris(["http://localhost:6274/callback"])
        assert not errors, f"Expected no errors, got: {errors}"

    def test_loopback_ip_allowed_in_development(self):
        """Loopback IP (127.0.0.1) redirect URIs are allowed when
        ALLOW_LOCALHOST_LOOPBACK=True."""
        errors = validate_redirect_uris(["http://127.0.0.1:6274/callback"])
        assert not errors, f"Expected no errors, got: {errors}"
