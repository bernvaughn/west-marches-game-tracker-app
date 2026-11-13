import re

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.views import serve
from django.test import Client, RequestFactory
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.story("U85")]

FONT = "fonts/im-fell-english-sc-latin-400-normal.woff2"


def _css(name):
    with open(finders.find(name), encoding="utf-8") as f:
        return f.read()


def test_font_and_licence_found_and_served():
    assert finders.find("fonts/OFL.txt")
    assert finders.find(FONT)
    settings.DEBUG = True
    r = serve(RequestFactory().get("/static/" + FONT), FONT)
    assert r.status_code == 200


def test_tokens_define_wordmark():
    css = _css("css/tokens.css")
    assert '"IM Fell English SC"' in css
    assert "--wm-font-wordmark" in css
    assert ".wm-wordmark" in css
    assert "../" + FONT in css
    assert "fonts.googleapis" not in css


def test_older_rules_do_not_override_wordmark_font():
    for name, sel in (("css/components.css", ".wm-side-menu .offcanvas-title"),
                      ("css/areas/accounts.css", ".wm-auth-brand")):
        rule = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", _css(name)).group(1)
        assert "font-family" not in rule


def test_side_menu_header_uses_wordmark(login, club, player):
    body = login(player).get(reverse("club_home", args=[club.slug])).content.decode()
    assert re.search(r'class="offcanvas-title wm-wordmark" id="site-menu-title"', body)


@pytest.mark.parametrize("name", ["login", "password_change"])
def test_auth_pages_use_wordmark(name, login, player):
    c = Client()
    if name == "password_change":
        c = login(player)
    body = c.get(reverse(name)).content.decode()
    assert 'class="wm-auth-brand wm-wordmark"' in body
    assert re.search(r"<h1[^>]*>", body)
    assert "wm-wordmark" not in re.search(r"<h1[^>]*>", body).group(0)


def test_logged_out_page_uses_wordmark(login, player):
    c = login(player)
    body = c.post(reverse("logout"), follow=True).content.decode()
    assert 'class="wm-auth-brand wm-wordmark"' in body
