"""Custom throttle classes for MCP/OAuth endpoints."""

from rest_framework.throttling import AnonRateThrottle


class AuthAnonThrottle(AnonRateThrottle):
    """Throttle for authentication endpoints (login, password reset)."""
    scope = "auth"


class OAuthAnonThrottle(AnonRateThrottle):
    """Throttle for OAuth endpoints (authorize, token)."""
    scope = "oauth"


class MCPAnonThrottle(AnonRateThrottle):
    """Throttle for MCP endpoints."""
    scope = "mcp"


class DCRAnonThrottle(AnonRateThrottle):
    """Throttle for Dynamic Client Registration endpoints."""
    scope = "dcr"