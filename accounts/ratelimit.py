"""Rate limiting utilities using Django's cache framework."""

from functools import wraps
from typing import Callable, Optional

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse


def get_client_ip(request: HttpRequest) -> str:
    """Extract the client IP address from the request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first IP in the chain (client IP)
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return ip


def get_rate_limit_key(
    prefix: str,
    identifier: str,
    window: int,
) -> str:
    """Generate a cache key for rate limiting."""
    return f"ratelimit:{prefix}:{identifier}:{window}"


def check_rate_limit(
    key: str,
    limit: int,
    window: int,
) -> tuple[bool, int, int]:
    """
    Check if the rate limit has been exceeded.

    Returns:
        tuple: (allowed, remaining, retry_after)
    """
    current = cache.get(key, 0)
    if current >= limit:
        # Some cache backends (like DummyCache) don't support ttl
        try:
            ttl = cache.ttl(key)
        except AttributeError:
            ttl = window
        retry_after = max(ttl, 1) if ttl > 0 else window
        return False, 0, retry_after

    # Increment the counter
    new_count = cache.incr(key) if current > 0 else 1
    if current == 0:
        # Some cache backends (like DummyCache) don't support expire
        try:
            cache.expire(key, window)
        except AttributeError:
            # Fallback: set with timeout
            cache.set(key, new_count, window)

    remaining = max(limit - new_count, 0)
    try:
        ttl = cache.ttl(key)
    except AttributeError:
        ttl = window
    retry_after = max(ttl, 1) if ttl > 0 else window
    return True, remaining, retry_after


def add_rate_limit_headers(response: HttpResponse, limit: int, remaining: int, retry_after: int) -> None:
    """Add rate limit headers to the response."""
    response["X-RateLimit-Limit"] = str(limit)
    response["X-RateLimit-Remaining"] = str(remaining)
    response["Retry-After"] = str(retry_after)


def rate_limit(
    prefix: str,
    limit: int,
    window: int,
    key_func: Optional[Callable[..., str]] = None,
):
    """
    Decorator to apply rate limiting to a view.

    Args:
        prefix: A prefix for the cache key (e.g., 'login', 'password_change')
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        key_func: Optional function to extract the rate limit key from the request.
                  Can accept the request and any view kwargs.
                  Defaults to client IP.
    """
    if key_func is None:
        key_func = get_client_ip

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            identifier = key_func(request, *args, **kwargs)
            cache_key = get_rate_limit_key(prefix, identifier, window)
            allowed, remaining, retry_after = check_rate_limit(cache_key, limit, window)

            if not allowed:
                response = HttpResponse(
                    "Rate limit exceeded. Please try again later.",
                    status=429,
                )
                add_rate_limit_headers(response, limit, remaining, retry_after)
                return response

            response = view_func(request, *args, **kwargs)
            add_rate_limit_headers(response, limit, remaining, retry_after)
            return response

        return wrapped

    return decorator


class RateLimitMixin:
    """
    Mixin to add rate limiting to class-based views.

    Subclasses must define:
        ratelimit_prefix: str - prefix for cache key
        ratelimit_limit: int - max requests allowed
        ratelimit_window: int - time window in seconds
        ratelimit_key_func: Optional[Callable] - function to extract key from request
    """

    ratelimit_prefix: str = ""
    ratelimit_limit: int = 5
    ratelimit_window: int = 60
    ratelimit_key_func: Optional[Callable[[HttpRequest], str]] = None

    def dispatch(self, request, *args, **kwargs):
        if not self.ratelimit_prefix:
            return super().dispatch(request, *args, **kwargs)

        if self.ratelimit_key_func is None:
            key_func = get_client_ip
        else:
            key_func = self.ratelimit_key_func

        identifier = key_func(request)
        cache_key = get_rate_limit_key(self.ratelimit_prefix, identifier, self.ratelimit_window)
        allowed, remaining, retry_after = check_rate_limit(
            cache_key, self.ratelimit_limit, self.ratelimit_window
        )

        if not allowed:
            response = HttpResponse(
                "Rate limit exceeded. Please try again later.",
                status=429,
            )
            add_rate_limit_headers(response, self.ratelimit_limit, remaining, retry_after)
            return response

        response = super().dispatch(request, *args, **kwargs)
        add_rate_limit_headers(response, self.ratelimit_limit, remaining, retry_after)
        return response