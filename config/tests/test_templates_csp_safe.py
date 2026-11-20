"""Static scan of templates for CSP-blocked inline scripts and handlers.

The site serves ``Content-Security-Policy: script-src 'self'`` (see
``config/settings.py``), so inline ``<script>`` blocks and inline
``on*="..."`` event attributes are blocked in production. The test settings
deliberately add ``'unsafe-inline'``, so the Django test suite itself cannot
catch regressions; this test scans the templates statically instead.

It walks every ``*.html`` under ``BASE_DIR/templates`` and each project
app's ``BASE_DIR/<app>/templates`` directory (third-party templates are
never scanned) and fails with a ``file:line`` list when it
finds:
  * a ``<script>`` tag without a ``src`` attribute (data blocks of type
    ``application/json`` or ``application/ld+json`` are allowed), or
  * any tag carrying an ``on<event>="..."`` attribute.

Django template comments (``{# #}`` and ``{% comment %}``) and ``{% verbatim %}
`` blocks are stripped first so live examples inside them are not flagged.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings

_VERBATIM_RE = re.compile(r"{% verbatim %}.*?{% endverbatim %}", re.DOTALL)
_COMMENT_RE = re.compile(r"{% comment %}.*?{% endcomment %}", re.DOTALL)
_BRACE_COMMENT_RE = re.compile(r"{#.*?#}", re.DOTALL)
_SCRIPT_START_RE = re.compile(r"<script\b", re.IGNORECASE)
_SRC_RE = re.compile(r"\bsrc\s*=", re.IGNORECASE)
_JSON_TYPE_RE = re.compile(r"\btype\s*=\s*[\"']application/(?:json|ld\+json)[\"']", re.IGNORECASE)
_ON_ATTR_RE = re.compile(r"\bon\w+\s*=", re.IGNORECASE)


def _blank_keep_newlines(match):
    """Replace a match with its newlines only, so line numbers stay right."""
    return "\n" * match.group(0).count("\n")


def _strip_template_marks(source):
    """Remove Django comments and verbatim blocks so they are not scanned."""
    source = _VERBATIM_RE.sub(_blank_keep_newlines, source)
    source = _COMMENT_RE.sub(_blank_keep_newlines, source)
    source = _BRACE_COMMENT_RE.sub(_blank_keep_newlines, source)
    return source


def scan_source(source, filename):
    """Return a list of ``filename:line: problem`` strings for one template."""
    source = _strip_template_marks(source)
    lines = source.splitlines()
    problems = []
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        lineno = i + 1
        match = _SCRIPT_START_RE.search(line)
        if match:
            start = match.start()
            end = line.find(">", match.end())
            if end == -1:
                # Tag continues on following lines; gather until ">" is found.
                tag = line[start:]
                j = i + 1
                while j < total and ">" not in lines[j]:
                    tag += lines[j]
                    j += 1
                if j < total:
                    tag += lines[j][: lines[j].find(">") + 1]
                    i = j
                else:
                    i = total
            else:
                tag = line[start : end + 1]
            if not _SRC_RE.search(tag) and not _JSON_TYPE_RE.search(tag):
                problems.append(f"{filename}:{lineno}: inline <script> tag without a src attribute")
            i += 1
            continue
        if _ON_ATTR_RE.search(line):
            problems.append(f"{filename}:{lineno}: inline on* event attribute")
        i += 1
    return problems


def _iter_template_files():
    """Yield every project ``*.html`` template.

    Only project templates are scanned: ``BASE_DIR/templates`` plus each
    top-level ``BASE_DIR/<app>/templates`` dir. Hidden dirs (such as a
    ``.venv`` inside the repo) are skipped, so third-party templates in
    ``site-packages`` are never scanned. We cannot fix those, and a library
    upgrade must not fail this test.
    """
    base = Path(settings.BASE_DIR)
    roots = [base / "templates"]
    for child in sorted(base.iterdir()):
        if child.name.startswith(".") or child.name in {"node_modules", "templates"}:
            continue
        if child.is_dir() and (child / "templates").is_dir():
            roots.append(child / "templates")
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.html")):
            if path.is_file():
                yield path


def _all_problems():
    problems = []
    for path in _iter_template_files():
        rel = path.relative_to(settings.BASE_DIR)
        problems.extend(scan_source(path.read_text(encoding="utf-8"), str(rel)))
    return problems


def test_scanner_flags_inline_script_and_event_attribute():
    """Self-test: the scanner must flag both an inline script and an onclick,
    and must not flag stripped-out comments or JSON data blocks."""
    source = (
        "{# <script>hidden()</script> #}\n"
        "{% comment %}<script>also_hidden()</script>{% endcomment %}\n"
        '<button onclick="x()">Click</button>\n'
        '<script type="application/json">{"a": 1}</script>\n'
        "<script>alert(1);</script>"
    )
    problems = scan_source(source, "fake.html")
    messages = "\n".join(problems)
    assert "inline <script> tag without a src attribute" in messages
    assert "inline on* event attribute" in messages
    # Exactly two real problems: the onclick line and the inline script line.
    assert len(problems) == 2


def test_scanner_keeps_line_numbers_after_multiline_comment():
    """Stripped multi-line comments must not shift the reported line."""
    source = "{% comment %}\none\ntwo\n{% endcomment %}\n<script>x()</script>"
    assert scan_source(source, "fake.html") == [
        "fake.html:5: inline <script> tag without a src attribute"
    ]


def test_only_project_templates_are_scanned():
    """Third-party templates (Django admin, site-packages) are out of scope."""
    base = Path(settings.BASE_DIR).resolve()
    paths = list(_iter_template_files())
    assert paths, "expected to find project templates"
    for path in paths:
        resolved = path.resolve()
        assert resolved.is_relative_to(base), resolved
        assert "site-packages" not in resolved.parts, resolved
        assert not any(part.startswith(".") for part in resolved.relative_to(base).parts), resolved


def test_templates_have_no_inline_scripts_or_event_attributes():
    """No template may contain an inline script or an on* handler while the
    CSP is script-src 'self'."""
    problems = _all_problems()
    if problems:
        problems.sort()
        pytest.fail(
            "CSP (script-src 'self') blocks inline scripts and event "
            "attributes. Found in templates:\n" + "\n".join(problems)
        )
