"""Security headers middleware for additional protection."""

from django.http import HttpResponse


class SecurityHeadersMiddleware:
    """Add security headers to all responses.

    Headers added:
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: restrictive defaults (disable most browser features)
    - Cross-Origin-Opener-Policy: same-origin
    - Cross-Origin-Embedder-Policy: require-corp
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self.add_security_headers(response)
        return response

    @staticmethod
    def add_security_headers(response: HttpResponse) -> None:
        """Add security headers to the response."""
        # Referrer-Policy: strict-origin-when-cross-origin
        # Sends origin, path, and query string for same-origin requests.
        # Sends only origin for cross-origin requests with same security level (HTTPS->HTTPS).
        # Sends no referrer for cross-origin requests to less secure destinations (HTTPS->HTTP).
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: restrictive defaults
        # Disables access to most browser features and APIs by default.
        # Features can be explicitly enabled per-origin if needed.
        response["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Cross-Origin-Opener-Policy: same-origin
        # Isolates the browsing context from cross-origin documents.
        # Prevents cross-origin documents from sharing the same browsing context group.
        response["Cross-Origin-Opener-Policy"] = "same-origin"

        # Cross-Origin-Embedder-Policy: require-corp
        # Requires cross-origin resources to explicitly opt-in via CORS or CORP headers.
        # Prevents loading of cross-origin resources that don't grant permission.
        response["Cross-Origin-Embedder-Policy"] = "require-corp"
