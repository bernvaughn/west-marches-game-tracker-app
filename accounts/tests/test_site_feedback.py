import re

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils.http import urlencode

from accounts.models import SiteFeedback, User

pytestmark = pytest.mark.story("U114")

NEW_URL = reverse("feedback_new")
LIST_URL = reverse("site_feedback")


def _status_url(pk):
    return reverse("site_feedback_status", args=[pk])


def _post(client, kind="bug", body="The shop page crashes on load.", **extra):
    data = {"kind": kind, "body": body}
    data.update(extra)
    return client.post(NEW_URL, data)


@pytest.mark.django_db
def test_player_posts_bug_and_feature(club, player, login):
    c = login(player)
    r = _post(c, "bug", "The map tile crashes on load.")
    assert r.status_code == 302
    bug = SiteFeedback.objects.get(kind="bug")
    assert bug.user == player
    assert bug.body == "The map tile crashes on load."
    assert bug.status == SiteFeedback.Status.OPEN
    assert bug.club is None
    assert bug.page_url == ""

    r = _post(c, "feature", "Add a dark mode.")
    assert r.status_code == 302
    feat = SiteFeedback.objects.get(kind="feature")
    assert feat.user == player
    assert feat.status == "open"
    assert SiteFeedback.objects.count() == 2


@pytest.mark.django_db
def test_club_taken_from_origin_page(club, player, login):
    c = login(player)
    from_url = reverse("club_home", args=[club.slug])
    c.post(
        NEW_URL + "?" + urlencode({"from": from_url}),
        {"kind": "bug", "body": "Crash in club."},
    )
    fb = SiteFeedback.objects.get()
    assert fb.club == club
    assert fb.page_url == from_url


@pytest.mark.django_db
def test_external_page_url_is_dropped(player, login):
    c = login(player)
    c.post(
        NEW_URL + "?" + urlencode({"from": "https://evil.example/evil"}),
        {"kind": "bug", "body": "x"},
    )
    assert SiteFeedback.objects.get().page_url == ""


@pytest.mark.django_db
def test_anonymous_redirects_and_saves_nothing(client):
    assert client.get(NEW_URL).status_code == 302
    assert client.post(NEW_URL, {"kind": "bug", "body": "x"}).status_code == 302
    assert SiteFeedback.objects.count() == 0


@pytest.mark.django_db
def test_invalid_input_saved_nothing(player, login):
    c = login(player)
    before = SiteFeedback.objects.count()
    for data in (
        {"kind": "bug", "body": ""},
        {"kind": "bug", "body": "x" * 2001},
        {"kind": "evil", "body": "x"},
    ):
        r = c.post(NEW_URL, data)
        assert r.status_code == 200, data
    assert SiteFeedback.objects.count() == before


@pytest.mark.django_db
def test_kind_preselected_from_query_param(player, login):
    body = login(player).get(NEW_URL + "?kind=feature").content.decode()
    assert "checked" in body
    assert "Bug: something in the app is broken" in body
    assert "Feature: something the app should do" in body


@pytest.mark.django_db
def test_form_page_wording(player, login):
    body = login(player).get(NEW_URL).content.decode()
    assert "Report a bug or suggest a feature" in body
    assert "not to your club's admins" in body
    assert "This form is for problems with the app" in body
    assert "Send to app admins" in body
    assert "Your earlier reports" in body


@pytest.mark.django_db
def test_own_reports_only_show_on_own_page(club, player, login):
    other = User.objects.create_user("other@example.com", password="pw", display_name="Other")
    c = login(player)
    _post(c, "bug", "Mine")
    assert "Mine" in c.get(NEW_URL).content.decode()
    assert "Mine" not in login(other).get(NEW_URL).content.decode()


@pytest.mark.django_db
def test_footer_links_visible_and_hidden(club, player, login):
    member = login(player)
    for path in (reverse("home"), reverse("club_home", args=[club.slug])):
        body = member.get(path, follow=True).content.decode()
        assert reverse("feedback_new") + "?kind=bug" in body
        assert reverse("feedback_new") + "?kind=feature" in body
        assert "Report a bug" in body
        assert "Suggest a feature" in body
    anonymous = Client()
    body = anonymous.get(reverse("login")).content.decode()
    assert reverse("feedback_new") not in body
    assert "Report a bug" not in body


@pytest.mark.django_db
def test_site_admin_sees_list_and_changes_status(site_admin, club, player, login):
    c = login(site_admin)
    SiteFeedback.objects.create(user=player, club=club, kind="bug", body="The tile crashes.")
    r = c.get(LIST_URL)
    assert r.status_code == 200
    body = r.content.decode()
    assert "The tile crashes." in body
    assert player.email in body

    fb = SiteFeedback.objects.get()
    r = c.post(_status_url(fb.pk), {"status": "handled"})
    assert r.status_code == 302
    assert SiteFeedback.objects.get().status == "handled"

    r = c.post(_status_url(fb.pk), {"status": "open"})
    assert r.status_code == 302
    assert SiteFeedback.objects.get().status == "open"


@pytest.mark.django_db
def test_site_admin_feedback_filters_are_labelled_and_table_is_phone_ready(
    site_admin, club, player, login
):
    c = login(site_admin)
    SiteFeedback.objects.create(
        user=player,
        club=club,
        kind="bug",
        body="The tile crashes.",
        page_url="https://example.com/a/very/long/page/url/that/should/not/push/report/off/screen",
    )
    r = c.get(LIST_URL)
    assert r.status_code == 200
    body = r.content.decode()

    # Labels are tied to their selects with for/id.
    assert 'for="feedback-status"' in body
    assert 'id="feedback-status"' in body
    assert 'for="feedback-kind"' in body
    assert 'id="feedback-kind"' in body

    # Filter controls wrap; the old non-wrapping inline-flex row is gone.
    assert "flex-wrap" in body
    assert "d-inline-flex" not in body

    # Low-value columns are optional; Report, Status and Kind stay visible.
    th_tags = re.findall(r"<th[^>]*>.*?</th>", body, re.S)
    optional = [t for t in th_tags if "wm-col-optional" in t]
    assert len(optional) == 4
    for label in ("User", "Club", "Page", "Date"):
        assert any(label in t for t in optional), label
    for label in ("Kind", "Status", "Report"):
        assert not any(label in t and "wm-col-optional" in t for t in th_tags), label

    # Action column has a visually hidden header.
    assert re.search(r'<th class="actions"><span class="visually-hidden">Actions</span></th>', body)


@pytest.mark.django_db
def test_club_admin_and_player_forbidden(site_admin, club_admin, player, club, login):
    SiteFeedback.objects.create(user=player, kind="bug", body="b")
    fb = SiteFeedback.objects.get()
    for u in (club_admin, player):
        c = login(u)
        assert c.get(LIST_URL).status_code == 403
        assert c.post(_status_url(fb.pk), {"status": "closed"}).status_code == 403
    assert Client().get(LIST_URL).status_code == 302


@pytest.mark.django_db
def test_rate_limit_returns_429_after_cap(player, login):
    with override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    ):
        c = login(player)
        url = NEW_URL + "?kind=bug"
        for _ in range(10):
            r = c.post(url, {"kind": "bug", "body": "x"})
            assert r.status_code == 302, r.status_code
        r = c.post(url, {"kind": "bug", "body": "x"})
        assert r.status_code == 429
