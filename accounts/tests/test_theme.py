import pytest
from django import forms
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.views import serve
from django.test import Client, RequestFactory
from django.urls import reverse

from config.form_renderer import BootstrapFormRenderer
from ledger.coins import CoinsField

CSS = "vendor/bootswatch-5.3.3/journal/bootstrap.min.css"
JS = "vendor/bootstrap-5.3.3/js/bootstrap.bundle.min.js"
FILES = [
    CSS,
    JS,
    "vendor/bootstrap-5.3.3/css/bootstrap.min.css",
    "vendor/bootstrap-5.3.3/LICENSE",
    "vendor/bootswatch-5.3.3/LICENSE",
]


@pytest.mark.story("U23")
@pytest.mark.django_db
def test_login_page_has_theme_and_no_cdn():
    html = Client().get(reverse("login")).content.decode()
    assert CSS in html and JS in html
    assert "form-control" in html
    assert "googleapis" not in html and "cdn" not in html.lower()


@pytest.mark.story("U23")
@pytest.mark.django_db
def test_password_pages_use_theme(player, login):
    client = login(player)
    html = client.get(reverse("password_change")).content.decode()
    assert CSS in html and "form-control" in html
    player.must_change_password = True
    player.save()
    html = client.get(reverse("password_change"), follow=True).content.decode()
    assert "alert-info" in html and "form-control" in html


@pytest.mark.story("U23")
@pytest.mark.parametrize("path", FILES)
def test_vendored_files_found_and_served(path, settings):
    assert finders.find(path)
    if path.endswith(("css", "js")):
        settings.DEBUG = True
        r = serve(RequestFactory().get("/static/" + path), path)
        assert r.status_code == 200


@pytest.mark.story("U23")
def test_vendored_journal_has_no_cdn():
    with open(finders.find(CSS), encoding="utf-8") as f:
        assert "fonts.googleapis" not in f.read()


@pytest.mark.story("U23")
@pytest.mark.django_db
def test_main_pages_render_themed(club, player, character, login):
    client = login(player)
    pages = [
        reverse("club_home", args=[club.slug]),
        reverse("characters:detail", args=[club.slug, character.pk]),
        reverse("ledger:index", args=[club.slug]),
        reverse("shops:index", args=[club.slug]),
        reverse("items:index", args=[club.slug]),
        reverse("map:index", args=[club.slug]),
    ]
    for url in pages:
        r = client.get(url)
        assert r.status_code == 200, url
        html = r.content.decode()
        assert CSS in html
        if "<table" in html:
            assert "table-sm" in html


@pytest.mark.story("U23")
@pytest.mark.django_db
def test_gm_and_admin_pages_render(club, game_master, club_admin, login):
    gm, admin = login(game_master), login(club_admin)
    for client, name in (
        (gm, "agent_access:batches"),
        (gm, "map:requests"),
        (admin, "accounts:message_inbox"),
    ):
        r = client.get(reverse(name, args=[club.slug]))
        assert r.status_code == 200 and CSS in r.content.decode()


@pytest.mark.story("U23")
@pytest.mark.django_db
def test_renderer_adds_bootstrap_classes():
    class F(forms.Form):
        name = forms.CharField(widget=forms.TextInput(attrs={"class": "mine"}))
        kind = forms.ChoiceField(choices=[("a", "A")])
        flag = forms.BooleanField(required=False)
        pick = forms.ChoiceField(choices=[("a", "A")], widget=forms.RadioSelect)
        coins = CoinsField(required=False)

    form = F(data={"kind": "zzz"}, renderer=BootstrapFormRenderer())
    html = form.as_p()
    for cls in ("form-control-sm", "form-select-sm", "form-check-input", "is-invalid"):
        assert cls in html
    assert "mine" in html and "form-control form-control-sm" in html
    assert html.count("form-control-sm") >= 5


@pytest.mark.story("U23")
@pytest.mark.django_db
def test_club_switcher_is_isolated(club, other_club, player, login):
    client = login(player)
    html = client.get(reverse("club_home", args=[club.slug])).content.decode()
    assert "Club A" in html and "Club B" not in html
    assert client.get(reverse("club_home", args=[other_club.slug])).status_code in (403, 404)
