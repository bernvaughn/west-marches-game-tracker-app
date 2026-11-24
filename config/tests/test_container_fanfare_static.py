"""Unit tests for container_fanfare static files served with content hash."""

from django.contrib.staticfiles.storage import staticfiles_storage


def test_container_fanfare_js_served_with_content_hash():
    """container_fanfare.js is served with a content-hash version query parameter."""
    url = staticfiles_storage.url("js/container_fanfare.js")
    assert url.startswith("/static/js/container_fanfare.js")
    assert "?v=" in url
    # Hash should be 12 hex chars (sha256 truncated)
    hash_part = url.split("?v=")[1]
    assert len(hash_part) == 12
    assert all(c in "0123456789abcdef" for c in hash_part)


def test_container_fanfare_css_served_with_content_hash():
    """container_fanfare.css is served with a content-hash version query parameter."""
    url = staticfiles_storage.url("css/container_fanfare.css")
    assert url.startswith("/static/css/container_fanfare.css")
    assert "?v=" in url
    hash_part = url.split("?v=")[1]
    assert len(hash_part) == 12
    assert all(c in "0123456789abcdef" for c in hash_part)


def test_container_fanfare_js_referenced_in_template():
    """container_fanfare.js is referenced in _fanfare_assets.html via {% static %}."""
    from pathlib import Path

    partial_html = (
        Path(__file__).resolve().parent.parent.parent
        / "player_characters"
        / "templates"
        / "player_characters"
        / "characters"
        / "_fanfare_assets.html"
    )
    content = partial_html.read_text()
    assert "js/container_fanfare.js" in content
    assert "{% static 'js/container_fanfare.js' %}" in content


def test_container_fanfare_css_referenced_in_template():
    """container_fanfare.css is referenced in _fanfare_assets.html via {% static %}."""
    from pathlib import Path

    partial_html = (
        Path(__file__).resolve().parent.parent.parent
        / "player_characters"
        / "templates"
        / "player_characters"
        / "characters"
        / "_fanfare_assets.html"
    )
    content = partial_html.read_text()
    assert "css/container_fanfare.css" in content
    assert "{% static 'css/container_fanfare.css' %}" in content


def test_container_fanfare_files_exist():
    """container_fanfare.js and .css files exist on disk."""
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent.parent
    js_path = base / "static" / "js" / "container_fanfare.js"
    css_path = base / "static" / "css" / "container_fanfare.css"
    assert js_path.is_file(), f"Missing: {js_path}"
    assert css_path.is_file(), f"Missing: {css_path}"
    # Should not be empty
    assert js_path.stat().st_size > 100
    assert css_path.stat().st_size > 100
