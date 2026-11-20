"""Tests for the message_new form polish (U60)."""

import re
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import formats

from accounts.models import Membership, Message


def _textarea_body(page):
    """Extract the textarea body from HTML."""
    match = re.search(r'<textarea[^>]*name="body"[^>]*>(.*?)</textarea>', page, re.DOTALL)
    return match.group(1).strip("\n") if match else ""


def _mem(user, club):
    return Membership.objects.get(user=user, club=club)


@pytest.fixture
def message(club, player, character):
    return Message.objects.create(
        club=club, sender=_mem(player, club), kind="message", body="Test message"
    )


@pytest.mark.story("U60")
def test_message_form_has_accessible_label(club, player, character, login):
    """The message box has an accessible label."""
    url = reverse("accounts:message_new", args=[club.slug])
    page = login(player).get(url).content.decode()

    # Check for label with for="id_body" containing "Message"
    assert 'for="id_body"' in page
    assert "Message" in page
    # Check textarea has id="id_body"
    assert 'id="id_body"' in page


@pytest.mark.story("U60")
def test_message_table_date_column_optional_and_under_message(
    club, player, character, message, login
):
    """Date column is hidden below 576px and date appears under message."""
    url = reverse("accounts:message_new", args=[club.slug])
    page = login(player).get(url).content.decode()

    # Date th has wm-col-optional
    assert '<th class="wm-col-optional">Date</th>' in page

    # Message cell contains date in small text-muted wm-date d-sm-none
    assert 'class="small text-muted wm-date d-sm-none"' in page
    # The date string should be present (Django's DATETIME_FORMAT is 'N j, Y, P')
    expected_date = formats.date_format(message.created, "DATETIME_FORMAT").lower()
    assert expected_date in page.lower()


@pytest.mark.story("U60")
def test_js_has_focus_and_selection(static_js_files):
    """inbox_templates.js contains focus() and setSelectionRange."""
    content = static_js_files["inbox_templates.js"]
    assert "focus()" in content
    assert "setSelectionRange" in content
    assert "input" in content  # dispatchEvent for input event
    assert "is-invalid" in content  # clearInvalid function


@pytest.fixture
def static_js_files():
    """Read static JS files for content checks."""
    base = Path(__file__).resolve().parents[2] / "static" / "js"
    return {
        "inbox_templates.js": (base / "inbox_templates.js").read_text(),
    }


@pytest.mark.story("U60")
def test_no_inline_script_or_handler(club, player, login):
    """Response has no inline script or onclick handlers."""
    url = reverse("accounts:message_new", args=[club.slug])
    page = login(player).get(url).content.decode()

    # No inline script without src - match <script> that doesn't have src attribute
    # This regex matches <script> tags without src=
    inline_scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", page, re.DOTALL)
    assert not inline_scripts, f"Found inline scripts: {inline_scripts}"
    # No onclick handlers
    assert "onclick=" not in page
