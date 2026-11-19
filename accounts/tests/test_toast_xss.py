"""Tests for the DOM-based XSS fix in static/js/toast.js.

showToast must assign the toast message with textContent, never by
interpolating user-controlled text into an innerHTML template.
"""

import re
from pathlib import Path

import pytest

TOAST_JS = Path(__file__).resolve().parents[2] / "static" / "js" / "toast.js"


def _source() -> str:
    return TOAST_JS.read_text()


@pytest.mark.story("S1")
def test_showToast_assigns_message_with_textContent():
    """The user-controlled message is set via textContent, not innerHTML."""
    source = _source()
    assert re.search(r"\.textContent\s*=\s*message\b", source), (
        "showToast must assign the message via textContent"
    )


@pytest.mark.story("S1")
def test_showToast_does_not_interpolate_message_into_innerHTML():
    """The message must never be interpolated into an innerHTML template literal."""
    source = _source()
    assert "${message}" not in source
    # innerHTML may still be used for static parts only (icon, close button).
    assert "toast.innerHTML" in source
    assert '<span class="wm-toast-message"></span>' in source
