import re

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from config.static_storage import VersionedStaticFilesStorage

pytestmark = pytest.mark.story("U79")


def test_logout_in_footer_outside_body(django_user_model):
    from django.template.loader import render_to_string
    html = render_to_string("partials/side_menu.html", {"user": django_user_model(), "club": None})
    assert html.count("<form") == 1
    body_end = html.index("</div>", html.index("offcanvas-body"))
    assert html.index("wm-side-menu-footer") > body_end
    footer = html[html.index("wm-side-menu-footer"):]
    assert "wm-menu-logout" in footer
    assert "wm-menu-logout" not in html[: html.index("wm-side-menu-footer")]


def test_css_scrolls_body():
    css = open(finders.find("css/components.css")).read()
    assert re.search(r"\.wm-side-menu \.offcanvas-body \{[^}]*overflow-y: auto", css)


def test_static_urls_versioned(client, db):
    html = client.get("/accounts/login/").content.decode()
    urls = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
    urls = [u for u in urls if u.split("?")[0].endswith((".css", ".js"))]
    assert urls
    for u in urls:
        assert re.search(r"\?v=[0-9a-f]{12}$", u), u


def test_storage_hash_changes_with_content(tmp_path, settings):
    settings.STATICFILES_DIRS = [tmp_path]
    f = tmp_path / "a.css"
    f.write_text("a")
    s = VersionedStaticFilesStorage()
    u1 = s.url("a.css")
    assert u1 == s.url("a.css")
    f.write_text("bb")
    assert s.url("a.css") != u1
    assert re.search(r"\?v=[0-9a-f]{12}#x$", s.url("a.css") + "#x")


def test_storage_missing_file(settings):
    assert "?v=" not in VersionedStaticFilesStorage().url("nope/missing.css")


def test_favicon(client, db):
    for n in ("favicon.svg", "favicon.ico"):
        assert finders.find(n)
    html = client.get("/accounts/login/").content.decode()
    assert "favicon.svg" in html and "favicon.ico" in html
    r = client.get("/favicon.ico")
    assert r.status_code == 302
    assert re.search(r"favicon\.ico\?v=", r["Location"])
    assert r["Location"] == static("favicon.ico")
