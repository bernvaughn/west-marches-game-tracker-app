import pytest

from accounts.tests._cdn_assert import assert_no_cdn


def test_no_cdn_check_ignores_csrf_token_containing_cdn():
    """A random CSRF token must not look like a CDN.

    Regression test for the flaky login-page test: the token `abcdnxyz`
    contains "cdn" but is not a CDN address, so the check must pass.
    """
    html = (
        '<input type="hidden" name="csrfmiddlewaretoken" value="abcdnxyz">'
        '<link rel="stylesheet" href="/static/vendor/css/app.css">'
    )
    assert_no_cdn(html)


def test_no_cdn_check_catches_real_cdn():
    """The check must still flag a real CDN address."""
    html = '<script src="https://cdn.jsdelivr.net/x.js"></script>'
    with pytest.raises(AssertionError):
        assert_no_cdn(html)
