"""Unit tests for accounts.ratelimit.get_client_ip."""

import pytest
from django.http import HttpRequest
from django.test import override_settings

from accounts.ratelimit import get_client_ip


def _request(**meta):
    request = HttpRequest()
    request.META.update(meta)
    return request


@pytest.mark.story("S2")
def test_get_client_ip_defaults_to_remote_addr():
    request = _request(
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
    )
    # Untrusted: ignore the spoofable X-Forwarded-For header
    assert get_client_ip(request) == "10.0.0.5"


@pytest.mark.story("S2")
def test_get_client_ip_remote_addr_fallback():
    request = _request(REMOTE_ADDR="10.0.0.5")
    assert get_client_ip(request) == "10.0.0.5"


@pytest.mark.story("S2")
def test_get_client_ip_unknown_when_no_addr():
    request = _request()
    assert get_client_ip(request) == "unknown"


@pytest.mark.story("S2")
@override_settings(RATELIMIT_TRUST_XFF=True)
def test_get_client_ip_trusts_xff_when_enabled():
    request = _request(
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
    )
    assert get_client_ip(request) == "1.2.3.4"


@pytest.mark.story("S2")
@override_settings(RATELIMIT_TRUST_XFF=True)
def test_get_client_ip_trusts_single_xff():
    request = _request(
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="1.2.3.4",
    )
    assert get_client_ip(request) == "1.2.3.4"


@pytest.mark.story("S2")
@override_settings(RATELIMIT_TRUST_XFF=True)
def test_get_client_ip_trusted_xff_falls_back_to_remote_addr():
    request = _request(REMOTE_ADDR="10.0.0.5")
    assert get_client_ip(request) == "10.0.0.5"
