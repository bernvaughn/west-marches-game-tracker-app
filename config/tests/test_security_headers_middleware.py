"""Tests for SecurityHeadersMiddleware."""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from config.middleware import SecurityHeadersMiddleware


class TestSecurityHeadersMiddleware:
    """Test that SecurityHeadersMiddleware adds the required security headers."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance with a simple get_response."""

        def get_response(request):
            return HttpResponse("OK")

        return SecurityHeadersMiddleware(get_response)

    @pytest.fixture
    def factory(self):
        """Create a request factory."""
        return RequestFactory()

    def test_referrer_policy_header(self, middleware, factory):
        """Test Referrer-Policy header is added with correct value."""
        request = factory.get("/")
        response = middleware(request)

        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_header(self, middleware, factory):
        """Test Permissions-Policy header is added with restrictive defaults."""
        request = factory.get("/")
        response = middleware(request)

        expected = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        assert response["Permissions-Policy"] == expected

    def test_cross_origin_opener_policy_header(self, middleware, factory):
        """Test Cross-Origin-Opener-Policy header is added."""
        request = factory.get("/")
        response = middleware(request)

        assert response["Cross-Origin-Opener-Policy"] == "same-origin"

    def test_cross_origin_embedder_policy_header(self, middleware, factory):
        """Test Cross-Origin-Embedder-Policy header is added."""
        request = factory.get("/")
        response = middleware(request)

        assert response["Cross-Origin-Embedder-Policy"] == "require-corp"

    def test_all_headers_present_on_response(self, middleware, factory):
        """Test all four security headers are present on every response."""
        request = factory.get("/")
        response = middleware(request)

        assert "Referrer-Policy" in response
        assert "Permissions-Policy" in response
        assert "Cross-Origin-Opener-Policy" in response
        assert "Cross-Origin-Embedder-Policy" in response

    def test_headers_on_post_request(self, middleware, factory):
        """Test headers are added on POST requests too."""
        request = factory.post("/", {"data": "test"})
        response = middleware(request)

        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response["Cross-Origin-Opener-Policy"] == "same-origin"

    def test_headers_on_error_response(self, middleware, factory):
        """Test headers are added on error responses (404, 500)."""

        def error_response(request):
            return HttpResponse("Not Found", status=404)

        middleware_404 = SecurityHeadersMiddleware(error_response)
        request = factory.get("/nonexistent")
        response = middleware_404(request)

        assert response.status_code == 404
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response["Cross-Origin-Opener-Policy"] == "same-origin"

    def test_headers_on_json_response(self, middleware, factory):
        """Test headers are added on JSON API responses."""
        request = factory.get("/api/test", HTTP_ACCEPT="application/json")
        response = middleware(request)

        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response["Permissions-Policy"] == (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

    def test_add_security_headers_static_method(self):
        """Test the static add_security_headers method directly."""
        response = HttpResponse("Test")
        SecurityHeadersMiddleware.add_security_headers(response)

        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response["Permissions-Policy"] == (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        assert response["Cross-Origin-Opener-Policy"] == "same-origin"
        assert response["Cross-Origin-Embedder-Policy"] == "require-corp"

    def test_middleware_chaining(self, factory):
        """Test middleware works when chained with other middleware."""

        def inner_response(request):
            return HttpResponse("Inner")

        def outer_middleware(get_response):
            def middleware(request):
                response = get_response(request)
                response["X-Custom"] = "test"
                return response

            return middleware

        # Create a chain: outer -> security -> inner
        security = SecurityHeadersMiddleware(inner_response)
        outer = outer_middleware(security)

        request = factory.get("/")
        response = outer(request)

        # All headers should be present
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response["Cross-Origin-Opener-Policy"] == "same-origin"
        assert response["X-Custom"] == "test"
