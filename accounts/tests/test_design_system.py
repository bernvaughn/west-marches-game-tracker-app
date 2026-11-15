import pathlib
import re

import pytest
from bs4 import BeautifulSoup
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.urls import get_resolver, reverse

from accounts.design_tokens import contrast_ratio, read_tokens
from scripts.screenshot_pages import PAGES, ROLES, demo_objects, extra_fixtures

pytestmark = [pytest.mark.story("U35"), pytest.mark.django_db]

ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPONENTS = sorted((ROOT / "templates" / "components").glob("*.html"))
URL = "site_design"


def component_name(path):
    stem = path.stem
    for suffix in ("_footer_close", "_footer", "_open", "_close", "_empty"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem.replace("_", "-")


# ---- Guard-rail tests for U84 UI rules ----

# Pages that are allowed to have a themed header (not using page_header) with a reason.
# Each entry: (template_path_suffix, reason)
THEMED_H1_ALLOWLIST = [
    ("characters/detail.html", "Character sheet keeps its boxed header per N-15"),
    ("characters/print.html", "Print page uses print-specific layout"),
    ("characters/print_item_choose.html", "Print page uses print-specific layout"),
]


def _all_template_paths():
    """Return all template files in the project."""
    return list(ROOT.rglob("templates/**/*.html"))


def _get_all_urls():
    """Get all named URL patterns that respond to GET."""
    resolver = get_resolver()
    urls = set()
    for pattern in resolver.url_patterns:
        if hasattr(pattern, "url_patterns"):
            if pattern.namespace == "admin":
                continue
            for p in pattern.url_patterns:
                if p.name and not hasattr(p, "url_patterns"):
                    urls.add(f"{pattern.namespace}:{p.name}" if pattern.namespace else p.name)
        elif pattern.name:
            urls.add(pattern.name)
    return urls


@pytest.fixture
def demo(db):
    call_command("seed_demo", verbosity=0)
    extra_fixtures()
    return demo_objects()


def _get_user(role, client):
    """Get user for a role, using ROLES mapping."""
    email = ROLES.get(role)
    if email is None:
        return None
    from accounts.models import User
    return User.objects.get(email=email)


def test_every_page_extends_base_html():
    """Every template extends base.html; no Django admin header (B-02)."""
    for template in _all_template_paths():
        content = template.read_text()
        # Skip partials and components that are included, not extended
        if template.name.startswith("_") or "components/" in str(template.relative_to(ROOT)):
            continue
        if "partials/" in str(template.relative_to(ROOT)) or "forms/" in str(template.relative_to(ROOT)):
            continue
        if template.name == "base.html":
            continue
        if "extends" not in content:
            # Check if it's a partial that gets included
            if "{% include" not in content and "{% block" in content:
                continue
            pytest.fail(f"Template {template.relative_to(ROOT)} does not extend base.html")


def test_no_django_admin_header(client, login, site_admin):
    """No page shows the Django admin header (B-02)."""
    # Check the four password reset pages specifically
    for url_name in ["password_reset", "password_reset_done", "password_reset_confirm", "password_reset_complete"]:
        try:
            url = reverse(url_name, args=["x", "bad"]) if url_name == "password_reset_confirm" else reverse(url_name)
        except Exception:
            url = reverse(url_name)
        resp = client.get(url)
        assert resp.status_code in (200, 302), f"{url_name} failed"
        html = resp.content.decode()
        assert "Django administration" not in html, f"{url_name} shows Django admin header"
        assert "wm-topbar" in html or "navbar" in html, f"{url_name} missing app top bar"


def test_every_page_has_exactly_one_h1(client, login, site_admin, demo):
    """Every rendered page has exactly one h1, from components/page_header (B-10, B-64)."""
    problems = []
    for page_def in PAGES:
        user = _get_user(page_def.role, client)
        if user is None:
            resp = client.get(page_def.url(demo))
        else:
            client.force_login(user)
            resp = client.get(page_def.url(demo))

        if resp.status_code != 200:
            continue

        soup = BeautifulSoup(resp.content, "html.parser")
        h1s = soup.find_all("h1")
        if len(h1s) != 1:
            problems.append(f"{page_def.name}: found {len(h1s)} h1 elements (expected 1)")
            continue

        # Check if the h1 is inside a page_header component
        h1 = h1s[0]
        page_header = h1.find_parent(class_="wm-page-header")
        if not page_header:
            # Check allowlist
            allowed = False
            for template_suffix, reason in THEMED_H1_ALLOWLIST:
                if template_suffix in page_def.name:
                    allowed = True
                    break
            if not allowed:
                problems.append(f"{page_def.name}: h1 not in wm-page-header (not using page_header component)")

    assert not problems, "\n".join(problems)


def test_td_actions_are_icon_buttons_with_tooltip():
    """Buttons in td.actions are icon buttons with a title tooltip (B-79)."""
    problems = []
    for template in _all_template_paths():
        # Skip admin templates
        if "django/contrib/admin" in str(template):
            continue
        content = template.read_text()
        # Look for td.actions containing button or a elements
        if "td.actions" in content or 'class="actions"' in content or "class='actions'" in content:
            # Check each td.actions block - use BeautifulSoup for better parsing
            soup = BeautifulSoup(content, "html.parser")
            for td in soup.find_all("td", class_="actions"):
                for btn in td.find_all(["button", "a"]):
                    # Check for icon button pattern
                    has_icon = btn.find("svg") is not None or "icon" in btn.get("class", [])
                    has_tooltip = btn.get("title") or btn.get("aria-label")
                    if not has_icon or not has_tooltip:
                        problems.append(f"{template.relative_to(ROOT)}: td.actions button/link missing icon or title/tooltip")

    assert not problems, "\n".join(problems)


def test_no_raw_date_formats():
    """No raw |date:"..." formats outside the shared format from S1 (B-52)."""
    problems = []
    # Allowed patterns: |date, |date:"DATETIME_FORMAT", |date:"j M Y" (the shared format)
    # Also allow the coins filter
    date_format_re = re.compile(r'\|date:\s*"[^"]*"')
    for template in _all_template_paths():
        # Skip admin templates
        if "django/contrib/admin" in str(template):
            continue
        content = template.read_text()
        for match in date_format_re.finditer(content):
            fmt = match.group(0)
            # Allow the standard formats
            if fmt in ('|date:"DATETIME_FORMAT"', '|date:"j M Y"', '|date:"DATE_FORMAT"'):
                continue
            # Allow if it's in a comment
            line_start = content.rfind("\n", 0, match.start()) + 1
            line = content[line_start:content.find("\n", match.end())]
            if "{#" in line and "#}" in line:
                continue
            # Allow ISO format for HTML date inputs (type="date" needs Y-m-d)
            context = content[max(0, match.start()-100):match.end()+100]
            if 'type="date"' in context or 'type="datetime-local"' in context:
                continue
            problems.append(f"{template.relative_to(ROOT)}:L{content[:match.start()].count(chr(10))+1}: raw date format {fmt}")

    assert not problems, "\n".join(problems)


def test_scrollable_pre_has_tabindex():
    """Scrollable pre blocks have tabindex="0" (B-55)."""
    problems = []
    for template in _all_template_paths():
        content = template.read_text()
        # Look for .wm-code-wrap pre or pre with overflow
        soup = BeautifulSoup(content, "html.parser")
        for pre in soup.find_all("pre"):
            # Check if it's in a wm-code-wrap or has overflow style
            parent = pre.find_parent(class_="wm-code-wrap")
            style = pre.get("style", "")
            if parent or "overflow" in style:
                if not pre.get("tabindex") == "0":
                    problems.append(f"{template.relative_to(ROOT)}: scrollable pre missing tabindex=\"0\"")

    assert not problems, "\n".join(problems)


def test_one_btn_primary_per_page(client, login, site_admin, demo):
    """One btn-primary per rendered page (B-25, B-69)."""
    problems = []
    for page_def in PAGES:
        user = _get_user(page_def.role, client)
        if user is None:
            resp = client.get(page_def.url(demo))
        else:
            client.force_login(user)
            resp = client.get(page_def.url(demo))

        if resp.status_code != 200:
            continue

        soup = BeautifulSoup(resp.content, "html.parser")
        primary_btns = soup.find_all(class_="btn-primary")
        # Count unique primary buttons (excluding duplicates from modals that aren't shown)
        visible_primary = [b for b in primary_btns if b.get("style") != "display: none" and "d-none" not in b.get("class", [])]
        if len(visible_primary) > 1:
            problems.append(f"{page_def.name}: {len(visible_primary)} btn-primary buttons (expected ≤1)")

    assert not problems, "\n".join(problems)


def test_reference_page_access(client, login, player, club_admin, site_admin):
    url = reverse(URL)
    r = client.get(url)
    assert r.status_code == 302 and "login" in r["Location"]
    assert login(player).get(url).status_code == 403
    assert login(club_admin).get(url).status_code == 403
    assert login(site_admin).get(url).status_code == 200


@pytest.fixture
def page(login, site_admin):
    return login(site_admin).get(reverse(URL)).content.decode()


def test_every_component_has_a_section(page):
    names = {component_name(p) for p in COMPONENTS}
    assert len(names) >= 13
    for name in names:
        assert f'id="component-{name}"' in page, name


def test_every_token_is_shown(page):
    tokens = read_tokens()
    assert len(tokens) > 40
    for name in tokens:
        assert f"<code>{name}</code>" in page, name


def test_every_component_documents_itself():
    for path in COMPONENTS:
        assert path.read_text().startswith("{% comment %}"), path.name


def test_page_loads_nothing_from_a_cdn(page):
    assert "googleapis" not in page and "cdn" not in page.lower()


def _hex(tokens, name):
    return tokens[f"--wm-{name}"]


def test_text_contrast_meets_aa():
    t = read_tokens()
    surfaces = ["surface", "surface-raised", "surface-sunken"]
    for fg in ("text", "text-muted", "accent"):
        for bg in surfaces:
            assert contrast_ratio(_hex(t, fg), _hex(t, bg)) >= 4.5, (fg, bg)
    for bg in ("accent", "accent-hover", "success", "danger"):
        assert contrast_ratio(_hex(t, "on-accent"), _hex(t, bg)) >= 4.5, bg
    for status in ("success", "warning", "danger", "info"):
        assert contrast_ratio(_hex(t, status), _hex(t, "surface")) >= 4.5, status
        assert contrast_ratio(_hex(t, status), _hex(t, f"{status}-bg")) >= 4.5, status
    for coin in ("cp", "sp", "gp"):
        assert contrast_ratio(_hex(t, f"coin-{coin}"), _hex(t, "surface")) >= 4.5, coin
    assert contrast_ratio(_hex(t, "coin-pp"), _hex(t, "coin-pp-bg")) >= 4.5


def test_shop_presets_read_with_light_and_dark_text():
    t = read_tokens()
    for name in ("parchment", "forest", "ember", "ocean", "violet", "slate"):
        assert contrast_ratio(_hex(t, "on-accent"), _hex(t, f"shop-{name}-deep")) >= 4.5, name
        assert contrast_ratio(_hex(t, "text"), _hex(t, f"shop-{name}-soft")) >= 4.5, name


def test_platinum_chip_is_readable_on_parchment():
    t = read_tokens()
    assert contrast_ratio(_hex(t, "coin-pp"), _hex(t, "coin-pp-bg")) >= 4.5
    # The dark chip itself stands out against the page (non-text contrast).
    assert contrast_ratio(_hex(t, "coin-pp-bg"), _hex(t, "surface")) >= 3
    assert contrast_ratio(_hex(t, "coin-pp-bg"), _hex(t, "surface-raised")) >= 3
    css = (ROOT / "static/css/coins.css").read_text()
    assert ".coin-gp::before" in css and "--wm-coin-dot-gp" in css


def test_character_switch_submits_on_change_with_noscript_fallback():
    html = (
        ROOT / "player_characters/templates/player_characters/characters/_selector.html"
    ).read_text()
    assert "onchange=" in html and "<noscript>" in html


def test_bootstrap_bridge_and_link_order():
    css = (ROOT / "static/css/tokens.css").read_text()
    assert "--bs-primary:" in css and "--bs-link-color-rgb:" in css
    base = (ROOT / "templates/base.html").read_text()
    order = [
        "bootswatch-5.3.3/journal",
        "css/tokens.css",
        "css/components.css",
        "css/areas/accounts.css",
        "css/areas/characters.css",
        "css/areas/catalogue.css",
        "css/areas/agent.css",
    ]
    positions = [base.index(x) for x in order]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    "path",
    [
        "vendor/bootstrap-icons-1.11.3/bootstrap-icons.svg",
        "vendor/bootstrap-icons-1.11.3/LICENSE",
        "vendor/source-serif-4/source-serif-4-latin-600-normal.woff2",
        "vendor/source-serif-4/source-serif-4-latin-700-normal.woff2",
        "vendor/source-serif-4/OFL.txt",
        "css/areas/accounts.css",
        "css/areas/characters.css",
        "css/areas/catalogue.css",
        "css/areas/agent.css",
    ],
)
def test_vendored_and_area_files_exist(path):
    assert finders.find(path)


def test_no_raw_hex_in_components_css():
    css = (ROOT / "static/css/components.css").read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", css)


def test_design_doc_names_everything():
    doc = (ROOT / "docs/design/DESIGN_SYSTEM.md").read_text()
    for path in COMPONENTS:
        assert component_name(path).replace("-", "_") in doc, path.name
    for group in ("Spacing", "Type", "Colour", "Radii", "Shadows", "Focus ring", "Coins"):
        assert group in doc, group
    assert "A-36" in doc


def test_no_batch_sample_or_screenshots_committed():
    names = [
        p.name
        for p in ROOT.rglob("*.png")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]
    assert names == []
# CI retry trigger