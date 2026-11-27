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
  * any tag carrying an ``on<event>="..."`` attribute, or
  * any tag carrying an ``hx-on`` or ``data-hx-on`` attribute, or
  * any Alpine ``x-*``, ``:attr``, or ``@event`` expression that the CSP
    build of Alpine cannot run (it has no ``new Function``).

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
# hx-on:click="..." and data-hx-on:click="..." (htmx 2.0 also uses hx-on::click)
_HX_ON_ATTR_RE = re.compile(r"(?:data-)?hx-on(?::|::)\w+\s*=", re.IGNORECASE)
# Alpine attribute names: x-show, x-text, x-init, x-model, :class, @click, etc.
_ALPINE_ATTR_RE = re.compile(
    r"(?:^|\s)(x-[\w-]+|:[\w-]+|@[\w-]+|x-bind:[\w-]+|x-on:[\w-]+)\s*=",
    re.IGNORECASE,
)
# Skip these Alpine attributes entirely (their values are not expressions).
# x-transition:* values are CSS transition classes, not JS expressions.
_ALPINE_SKIP_PREFIXES = ("x-for", "x-transition", ":enter", ":leave")
# Capture the value of an attribute (quoted)
_ATTR_VALUE_RE = re.compile(r'\s*"([^"]*)"')


def _blank_keep_newlines(match):
    """Replace a match with its newlines only, so line numbers stay right."""
    return "\n" * match.group(0).count("\n")


def _strip_template_marks(source):
    """Remove Django comments and verbatim blocks so they are not scanned."""
    source = _VERBATIM_RE.sub(_blank_keep_newlines, source)
    source = _COMMENT_RE.sub(_blank_keep_newlines, source)
    source = _BRACE_COMMENT_RE.sub(_blank_keep_newlines, source)
    return source


def _alpine_needs_eval(expression):
    """Return True if an Alpine expression needs eval (CSP build cannot run it).

    The CSP build of Alpine supports only property paths and simple calls:
    ``foo``, ``foo.bar``, ``foo()``, ``foo.bar()``, ``foo(arg)``.
    Operators, object literals, array literals, and ternaries need eval.
    """
    # Strip string literals so quotes inside them don't trigger false positives.
    expr = re.sub(r"'[^']*'", "''", expression)
    expr = re.sub(r'"[^"]*"', '""', expr)
    # Strip simple property paths and method calls (these are safe).
    expr = re.sub(r"\b[a-zA-Z_][\w\.]*\s*\(\s*[a-zA-Z_][\w\.]*\s*\)", "()", expr)
    expr = re.sub(r"\b[a-zA-Z_][\w\.]*", "x", expr)
    # What remains should be punctuation only. Flag anything complex.
    if re.search(r"&&|\|\|", expr):
        return True
    if re.search(r"===|!==|==|!=", expr):
        return True
    if re.search(r"[+\-*/%]", expr):
        return True
    if re.search(r"(?:^|[^\w])!", expr):
        return True
    if re.search(r"\?", expr):
        return True
    if re.search(r"\{", expr):
        return True
    if re.search(r"\[", expr):
        return True
    if re.search(r"\bnew\b", expr):
        return True
    if "`" in expr:
        return True
    return False


def _extract_attr_values(line, attr_re):
    """Yield (attr_name, attr_value) for every attribute matching attr_re on a line."""
    for match in attr_re.finditer(line):
        attr_name = match.group(1)
        start = match.end()
        value_match = _ATTR_VALUE_RE.match(line[start:])
        if value_match:
            yield attr_name, value_match.group(1)


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
        if _HX_ON_ATTR_RE.search(line):
            problems.append(f"{filename}:{lineno}: hx-on attribute needs eval (CSP blocks it)")
        # Alpine expressions that the CSP build cannot run
        if filename not in _ALPINE_EVAL_SKIP_TEMPLATES:
            for attr_name, attr_value in _extract_attr_values(line, _ALPINE_ATTR_RE):
                if any(attr_name.startswith(p) for p in _ALPINE_SKIP_PREFIXES):
                    continue
                if _alpine_needs_eval(attr_value):
                    msg = f"{filename}:{lineno}: Alpine expression needs eval: {attr_name}"
                    problems.append(msg)
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


def _static_js_files():
    """Return the set of file names in static/js/."""
    base = Path(settings.BASE_DIR)
    js_dir = base / "static" / "js"
    if not js_dir.is_dir():
        return set()
    return {p.name for p in js_dir.glob("*.js") if p.is_file()}


def _referenced_js_files():
    """Return the set of js/ file names referenced in templates via {% static %}."""
    referenced = set()
    pattern = re.compile(r"{%\s*static\s+['\"]js/([^'\"]+)['\"]")
    for path in _iter_template_files():
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            referenced.add(match.group(1))
    return referenced


#: JS files that are loaded by other scripts (not directly by templates).
#: These are exempt from the "every static/js file must be referenced" test.
_JS_ALLOW_LIST = frozenset(
    {
        "player_items_merge.js",
        "player_items_review.js",
    }
)

#: Templates with known Alpine expressions that need eval but are being
#: fixed by a sibling task (command palette). These are excluded from the
#: Alpine eval check until that task lands. Do not add to this list without
#: coordinating with the command palette task.
_ALPINE_EVAL_SKIP_TEMPLATES = frozenset({"templates/components/command_palette.html"})

#: Inline style attributes are blocked by ``style-src 'self'`` (a nonce does
#: not cover style attributes). These templates keep them deliberately: the
#: values are dynamic design tokens, covered by a per-view
#: ``style-src-attr 'unsafe-inline'`` exception instead.
_STYLE_ALLOW_LIST = frozenset({"accounts/templates/accounts/design/reference.html"})

#: style="..." attribute (quoted).
_STYLE_ATTR_RE = re.compile(r'\bstyle\s*=\s*"')


def _style_attr_lines(source):
    """Return line numbers of ``style="`` attributes (comments/verbatim stripped)."""
    source = _strip_template_marks(source)
    return [i + 1 for i, line in enumerate(source.splitlines()) if _STYLE_ATTR_RE.search(line)]


def test_scanner_flags_inline_style_attribute():
    """Self-test: the scanner must flag a style attribute and not flag one
    inside a stripped comment or verbatim block."""
    source = (
        '{# <span style="color:red">hidden</span> #}\n'
        '{% verbatim %}<span style="color:red">hidden</span>{% endverbatim %}\n'
        '<span style="color:red">blocked</span>\n'
        '<span class="ok">plain</span>\n'
    )
    problems = _style_attr_lines(source)
    assert problems == [3]


def test_templates_have_no_inline_style_attributes():
    """No project template (except mail/ and the design reference view) may
    carry an inline style attribute while the CSP is style-src 'self'."""
    problems = []
    for path in _iter_template_files():
        rel = path.relative_to(settings.BASE_DIR)
        if rel.parts[0] == "mail":
            continue  # email clients are not served under the site CSP
        rel_str = str(rel)
        for lineno in _style_attr_lines(path.read_text(encoding="utf-8")):
            if rel_str in _STYLE_ALLOW_LIST:
                continue
            problems.append(f"{rel_str}:{lineno}: inline style attribute")
    base = Path(settings.BASE_DIR)
    for path in sorted((base / "static" / "js").glob("*.js")):
        for lineno in _style_attr_lines(path.read_text(encoding="utf-8")):
            problems.append(f"static/js/{path.name}:{lineno}: inline style attribute")
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / "forms.py").is_file():
            path = child / "forms.py"
            for lineno in _style_attr_lines(path.read_text(encoding="utf-8")):
                problems.append(f"{path.relative_to(base)}:{lineno}: inline style attribute")
    if problems:
        problems.sort()
        pytest.fail(
            "CSP (style-src 'self') blocks inline style attributes. Found in:\n"
            + "\n".join(problems)
            + "\nUse a class (fixed set) or the simplest working option for dynamic "
            "values; add style-src-attr 'unsafe-inline' only per-view, never site-wide."
        )


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


def test_scanner_flags_hx_on_attribute():
    """Self-test: the scanner must flag hx-on attributes."""
    source = (
        '<a hx-on:click="event.preventDefault()">link</a>\n'
        '<a data-hx-on:click="event.preventDefault()">link2</a>\n'
        '<a hx-on::click="event.preventDefault()">link3</a>\n'
        '<a href="/x">plain link</a>\n'
    )
    problems = scan_source(source, "fake.html")
    messages = "\n".join(problems)
    assert "hx-on attribute needs eval" in messages
    # Exactly three hx-on problems, no false positive on the plain link.
    hx_problems = [p for p in problems if "hx-on attribute" in p]
    assert len(hx_problems) == 3


def test_scanner_flags_alpine_needs_eval():
    """Self-test: the scanner must flag Alpine expressions needing eval."""
    source = (
        '<div x-show="open">ok</div>\n'
        '<div x-show="filtered.length === 0 && query">bad</div>\n'
        '<div :class="{ active: isActive }">bad2</div>\n'
        "<div x-text=\"'No results for ' + query\">bad3</div>\n"
        '<button @click="close()">ok2</button>\n'
        '<template x-for="item in items">skip</template>\n'
        '<div x-transition:enter="ease-out">skip2</div>\n'
    )
    problems = scan_source(source, "fake.html")
    messages = "\n".join(problems)
    assert "Alpine expression needs eval" in messages
    alpine_problems = [p for p in problems if "Alpine expression needs eval" in p]
    # Three bad expressions flagged; the safe ones and skipped ones are not.
    assert len(alpine_problems) == 3


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


def test_every_static_js_file_is_referenced():
    """Every file in static/js/ must be referenced by a template via
    {% static 'js/<name>' %}. Files loaded by other scripts go in
    _JS_ALLOW_LIST."""
    js_files = _static_js_files()
    referenced = _referenced_js_files()
    unreferenced = js_files - referenced - _JS_ALLOW_LIST
    if unreferenced:
        pytest.fail(
            "These static/js/*.js files are not referenced by any template:\n"
            + "\n".join(sorted(unreferenced))
            + "\nAdd them to a template, delete them, or list them in _JS_ALLOW_LIST."
        )


def test_no_unreferenced_js_files_in_allow_list():
    """The _JS_ALLOW_LIST must not contain files that are actually referenced."""
    allow_listed_and_referenced = _JS_ALLOW_LIST & _referenced_js_files()
    if allow_listed_and_referenced:
        pytest.fail(
            "_JS_ALLOW_LIST contains files that are referenced by templates:\n"
            + "\n".join(sorted(allow_listed_and_referenced))
            + "\nRemove them from the allow list."
        )
