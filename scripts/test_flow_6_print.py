"""Browser-free tests for the pure helpers in scripts/flow_checks/flow_6_print.py."""

from scripts.flow_checks.flow_6_print import (
    count_pdf_pages,
    has_inline_handler,
    pack_flags,
    pack_url,
    print_origin,
)


class MockElement:
    """Mock Playwright element for testing has_inline_handler."""

    def __init__(self, attrs: dict[str, str]):
        self._attrs = attrs

    def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)


def test_print_origin_chromium_stack():
    """Chromium stack format includes file paths."""
    stack = """Error
    at window.print (https://example.com/static/js/print_sheet.js:42:15)
    at HTMLButtonElement.<anonymous> (https://example.com/static/js/print_sheet.js:10:5)"""
    assert print_origin(stack) == "/static/js/print_sheet.js"


def test_print_origin_firefox_stack():
    """Firefox stack format includes file paths."""
    stack = """print@https://example.com/static/js/print_frame.js:25:3
handleSubmit@https://example.com/static/js/print_frame.js:10:5"""
    assert print_origin(stack) == "/static/js/print_frame.js"


def test_print_origin_inline_handler():
    """Inline handler (page URL) gives None."""
    stack = """Error
    at window.print (https://example.com/c/demo/characters/1/:1:1)
    at HTMLButtonElement.onclick (https://example.com/c/demo/characters/1/:1:1)"""
    assert print_origin(stack) is None


def test_print_origin_no_static_js():
    """Stack without /static/js/ gives None."""
    stack = """Error
    at window.print (https://example.com/some/other/path.js:1:1)"""
    assert print_origin(stack) is None


def test_print_origin_none():
    """None stack gives None."""
    assert print_origin(None) is None


def test_print_origin_empty():
    """Empty stack gives None."""
    assert print_origin("") is None


def test_count_pdf_pages_simple():
    """Count /Type /Page in a minimal PDF."""
    # Minimal PDF with 2 pages
    pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R >>
endobj
4 0 obj
<< /Type /Page /Parent 2 0 R >>
endobj
xref
0 5
0000000000 65535 f
trailer
<< /Size 5 /Root 1 0 R >>
startxref
%%EOF"""
    assert count_pdf_pages(pdf) == 2


def test_count_pdf_pages_zero():
    """Empty PDF gives 0."""
    assert count_pdf_pages(b"") == 0
    assert count_pdf_pages(b"%PDF-1.4\n%%EOF") == 0


def test_count_pdf_pages_not_pages():
    """Only count /Type /Page, not /Type /Pages."""
    pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R >>
endobj
xref
0 4
0000000000 65535 f
trailer
<< /Size 4 /Root 1 0 R >>
startxref
%%EOF"""
    assert count_pdf_pages(pdf) == 1


def test_pack_flags_empty():
    """No query gives all zeros."""
    assert pack_flags("/path") == {"sheet": 0, "items": 0, "quests": 0, "map": 0}
    assert pack_flags("/path?") == {"sheet": 0, "items": 0, "quests": 0, "map": 0}


def test_pack_flags_parses_correctly():
    """Parse ?sheet=1&items=0&quests=1&map=0."""
    url = "/c/demo/characters/1/print-session-pack/?sheet=1&items=0&quests=1&map=0"
    assert pack_flags(url) == {"sheet": 1, "items": 0, "quests": 1, "map": 0}


def test_pack_flags_partial():
    """Partial query gives zeros for missing."""
    url = "/path?sheet=1&map=1"
    assert pack_flags(url) == {"sheet": 1, "items": 0, "quests": 0, "map": 1}


def test_pack_url_builds_correctly():
    """Build URL with flags."""
    assert (
        pack_url("/path", sheet=1, items=0, quests=1, map=0)
        == "/path?sheet=1&items=0&quests=1&map=0"
    )
    assert (
        pack_url("/path", sheet=1, items=1, quests=1, map=1)
        == "/path?sheet=1&items=1&quests=1&map=1"
    )
    assert pack_url("/path") == "/path"


def test_has_inline_handler_onclick():
    """Detect onclick attribute."""
    el = MockElement({"onclick": "foo()", "id": "btn"})
    assert has_inline_handler(el) is True


def test_has_inline_handler_onsubmit():
    """Detect onsubmit attribute."""
    el = MockElement({"onsubmit": "return validate()", "class": "form"})
    assert has_inline_handler(el) is True


def test_has_inline_handler_other_on():
    """Detect other on* attributes."""
    for attr in ("onmousedown", "onmouseup", "onkeydown", "onkeyup", "onkeypress"):
        el = MockElement({attr: "handler()"})
        assert has_inline_handler(el) is True, f"failed for {attr}"


def test_has_inline_handler_none():
    """No on* attribute gives False."""
    el = MockElement({"id": "btn", "class": "btn", "data-print-sheet": "true"})
    assert has_inline_handler(el) is False


def test_has_inline_handler_empty_attr():
    """Empty on* attribute still counts."""
    el = MockElement({"onclick": "", "id": "btn"})
    assert has_inline_handler(el) is True


def test_split_known_separates_filed_bug():
    from scripts.flow_checks.flow_6_print import split_known

    known_line = (
        "@1280: console error: Bootstrap doesn't allow more than one instance per element. "
        "Bound instance: bs.tooltip."
    )
    new, known = split_known([known_line, "@1280: http 500 /x"])
    assert new == ["@1280: http 500 /x"]
    assert len(known) == 1 and "01a22132" in known[0]
