"""Tests for the character sheet sections registry and tag."""

import pytest
from django.template import Context, Template
from django.test import RequestFactory
from django.urls import reverse

from player_characters.models import Character
from player_characters import sheet_sections
from player_characters.templatetags.character_tags import sheet_sections as sheet_sections_tag


@pytest.fixture(autouse=True)
def _clear_sections():
    """Clear sections before and after each test."""
    sheet_sections._clear_sections()
    yield
    sheet_sections._clear_sections()


def u(name, club, pk=None):
    kw = {"club_slug": club.slug}
    if pk is not None:
        kw["pk"] = pk
    return reverse(name, kwargs=kw)


@pytest.fixture
def character(club, player):
    owner = player  # player is a Membership in the conftest
    return Character.objects.create(club=club, owner=owner, name="Aria")


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def demo_template(tmp_path, settings):
    """Create a temporary template directory for test templates."""
    template_dir = tmp_path / "templates" / "player_characters" / "tests"
    template_dir.mkdir(parents=True)
    demo_path = template_dir / "demo_section.html"
    demo_path.write_text(
        '<div class="demo-section">{{ demo_value }}</div>',
    )
    settings.TEMPLATES[0]["DIRS"].insert(0, str(tmp_path / "templates"))
    return "player_characters/tests/demo_section.html"


@pytest.mark.story("C2")
def test_order_kept():
    """Sections are returned sorted by order, then by key."""
    sheet_sections.register_sheet_section("third", 30, "t.html", lambda r, c: {})
    sheet_sections.register_sheet_section("first", 10, "t.html", lambda r, c: {})
    sheet_sections.register_sheet_section("second", 20, "t.html", lambda r, c: {})

    result = sheet_sections.get_sheet_sections(None, None)
    keys = [s["key"] for s in result]
    assert keys == ["first", "second", "third"]


@pytest.mark.story("C2")
def test_equal_order_sorts_by_key():
    """Equal order values are broken by key."""
    sheet_sections.register_sheet_section("b", 10, "t.html", lambda r, c: {})
    sheet_sections.register_sheet_section("a", 10, "t.html", lambda r, c: {})

    result = sheet_sections.get_sheet_sections(None, None)
    keys = [s["key"] for s in result]
    assert keys == ["a", "b"]


@pytest.mark.story("C2")
def test_visible_fn_false_hides_section(request_factory, character):
    """visible_fn returning False hides the section."""
    sheet_sections.register_sheet_section(
        "hidden",
        10,
        "t.html",
        lambda r, c: {"value": "should not appear"},
        visible_fn=lambda r, c: False,
    )
    sheet_sections.register_sheet_section(
        "visible",
        20,
        "t.html",
        lambda r, c: {"value": "should appear"},
        visible_fn=lambda r, c: True,
    )

    request = request_factory.get("/")
    result = sheet_sections.get_sheet_sections(request, character)
    keys = [s["key"] for s in result]
    assert keys == ["visible"]


@pytest.mark.story("C2")
def test_context_fn_none_skips_section(request_factory, character):
    """context_fn returning None skips the section."""
    sheet_sections.register_sheet_section(
        "skipped",
        10,
        "t.html",
        lambda r, c: None,
    )
    sheet_sections.register_sheet_section(
        "shown",
        20,
        "t.html",
        lambda r, c: {"value": "appears"},
    )

    request = request_factory.get("/")
    result = sheet_sections.get_sheet_sections(request, character)
    keys = [s["key"] for s in result]
    assert keys == ["shown"]


@pytest.mark.story("C2")
def test_visible_fn_exception_does_not_break_sheet(request_factory, character):
    """Exception in visible_fn is logged and section is skipped; others render."""
    def bad_visible(r, c):
        raise ValueError("boom")

    sheet_sections.register_sheet_section(
        "broken",
        10,
        "t.html",
        lambda r, c: {"value": "broken"},
        visible_fn=bad_visible,
    )
    sheet_sections.register_sheet_section(
        "ok",
        20,
        "t.html",
        lambda r, c: {"value": "ok"},
    )

    request = request_factory.get("/")
    result = sheet_sections.get_sheet_sections(request, character)
    keys = [s["key"] for s in result]
    assert keys == ["ok"]


@pytest.mark.story("C2")
def test_context_fn_exception_does_not_break_sheet(request_factory, character):
    """Exception in context_fn is logged and section is skipped; others render."""
    def bad_context(r, c):
        raise ValueError("boom")

    sheet_sections.register_sheet_section(
        "broken",
        10,
        "t.html",
        bad_context,
    )
    sheet_sections.register_sheet_section(
        "ok",
        20,
        "t.html",
        lambda r, c: {"value": "ok"},
    )

    request = request_factory.get("/")
    result = sheet_sections.get_sheet_sections(request, character)
    keys = [s["key"] for s in result]
    assert keys == ["ok"]


@pytest.mark.story("C2")
def test_no_sections_returns_empty(request_factory, character):
    """get_sheet_sections returns empty list when nothing registered."""
    request = request_factory.get("/")
    result = sheet_sections.get_sheet_sections(request, character)
    assert result == []


@pytest.mark.story("C2")
def test_tag_returns_empty_when_no_request_or_character():
    """sheet_sections tag returns empty string without request/character."""
    assert sheet_sections_tag(Context({})) == ""
    assert sheet_sections_tag(Context({"request": "x"})) == ""
    assert sheet_sections_tag(Context({"character": "x"})) == ""


@pytest.mark.story("C2")
def test_sheet_renders_sections_after_ledger(club, login, player, character, demo_template):
    """Sheet page includes registered sections after the ledger box."""
    def ctx_fn(r, c):
        return {"demo_value": "Hello from section"}

    sheet_sections.register_sheet_section("demo", 10, demo_template, ctx_fn)

    url = u("characters:detail", club, character.pk)
    html = login(player).get(url).content.decode()

    # Ledger box exists
    assert "Recent ledger entries" in html
    # Our demo section appears
    assert "Hello from section" in html
    # Demo section comes after ledger box
    ledger_idx = html.index("Recent ledger entries")
    demo_idx = html.index("Hello from section")
    assert demo_idx > ledger_idx
    # Wrapper has no-print and data-sheet-section
    assert 'data-sheet-section="demo"' in html
    assert "no-print" in html


@pytest.mark.story("C2")
def test_sheet_no_sections_no_extra_markup(club, login, player, character):
    """Sheet renders normally when no sections are registered."""
    url = u("characters:detail", club, character.pk)
    html = login(player).get(url).content.decode()
    assert "Recent ledger entries" in html
    assert "data-sheet-section" not in html


@pytest.mark.story("C2")
def test_wrapper_has_no_print_class(club, login, player, character, demo_template):
    """The section wrapper carries the no-print class."""
    sheet_sections.register_sheet_section(
        "demo", 10, demo_template, lambda r, c: {"demo_value": "x"}
    )
    url = u("characters:detail", club, character.pk)
    html = login(player).get(url).content.decode()

    # Find the section wrapper for our demo section
    import re
    match = re.search(r'data-sheet-section="demo"[^>]*class="([^"]*)"', html)
    assert match, "data-sheet-section attribute not found"
    classes = match.group(1)
    assert "no-print" in classes
    assert "wm-sheet-box" in classes
    assert "wm-sheet-full" in classes


@pytest.mark.story("C2")
def test_visible_fn_receives_request_and_character(request_factory, character):
    """visible_fn is called with (request, character)."""
    captured = {}

    def visible_fn(r, c):
        captured["request"] = r
        captured["character"] = c
        return True

    sheet_sections.register_sheet_section(
        "demo", 10, "t.html", lambda r, c: {}, visible_fn=visible_fn
    )

    request = request_factory.get("/")
    sheet_sections.get_sheet_sections(request, character)

    assert captured["request"] is request
    assert captured["character"] is character


@pytest.mark.story("C2")
def test_context_fn_receives_request_and_character(request_factory, character):
    """context_fn is called with (request, character)."""
    captured = {}

    def ctx_fn(r, c):
        captured["request"] = r
        captured["character"] = c
        return {"ok": True}

    sheet_sections.register_sheet_section("demo", 10, "t.html", ctx_fn)

    request = request_factory.get("/")
    sheet_sections.get_sheet_sections(request, character)

    assert captured["request"] is request
    assert captured["character"] is character


@pytest.mark.story("C2")
def test_section_context_reaches_template(club, login, player, character, demo_template):
    """The context from context_fn reaches the section template."""
    sheet_sections.register_sheet_section(
        "demo", 10, demo_template, lambda r, c: {"demo_value": "PASS"}
    )

    url = u("characters:detail", club, character.pk)
    html = login(player).get(url).content.decode()
    assert "PASS" in html


@pytest.mark.story("C2")
def test_two_sections_render_in_order(club, login, player, character, demo_template):
    """Multiple sections render in the correct order."""
    sheet_sections.register_sheet_section(
        "first", 10, demo_template, lambda r, c: {"demo_value": "FIRST"}
    )
    sheet_sections.register_sheet_section(
        "second", 20, demo_template, lambda r, c: {"demo_value": "SECOND"}
    )

    url = u("characters:detail", club, character.pk)
    html = login(player).get(url).content.decode()

    first_idx = html.index("FIRST")
    second_idx = html.index("SECOND")
    assert first_idx < second_idx


@pytest.mark.story("C2")
def test_repeated_key_replaces_old_entry(request_factory, character):
    """Registering the same key twice replaces the old entry."""
    sheet_sections.register_sheet_section(
        "demo", 10, "t.html", lambda r, c: {"value": "old"}
    )
    sheet_sections.register_sheet_section(
        "demo", 20, "t.html", lambda r, c: {"value": "new"}
    )

    request = request_factory.get("/")
    result = sheet_sections.get_sheet_sections(request, character)
    assert len(result) == 1
    assert result[0]["context"]["value"] == "new"
    assert result[0]["order"] == 20