"""Assert "no outside CDN" in a way that random CSRF tokens cannot break.

A CSRF token is a random string, so a bare substring check for "cdn" on
whole-page HTML fails whenever the token happens to contain those letters
(about 1 run in 500 for a 64-char token). These helpers strip the token value
first, then look only for real CDN addresses.
"""

import re

# Real CDN addresses. A bare word such as "cdn" is too short: a random token
# can contain it and cause a false failure.
_CDN_PATTERNS = ("//cdn.", "cdn.jsdelivr", "cdnjs", "unpkg", "googleapis")

_CSRF_TOKEN_RE = re.compile(r'(name="csrfmiddlewaretoken"\s+value=)"[^"]*"', re.IGNORECASE)


def strip_csrf_token(html: str) -> str:
    """Return *html* with the CSRF token value blanked out."""
    return _CSRF_TOKEN_RE.sub(r'\1""', html)


def assert_no_cdn(html: str) -> None:
    """Assert *html* loads nothing from an outside CDN.

    The CSRF token value is stripped first so a random token can never trigger
    a false positive. Only real CDN addresses are flagged.
    """
    cleaned = strip_csrf_token(html)
    lowered = cleaned.lower()
    for pattern in _CDN_PATTERNS:
        assert pattern not in lowered, f"Page loads from a CDN: {pattern}"
