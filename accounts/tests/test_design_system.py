import pathlib
import re

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from accounts.design_tokens import contrast_ratio, read_tokens

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
