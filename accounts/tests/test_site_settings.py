import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import SiteSettings

URL = "https://example.com/donate"


def body(client, path):
    return client.get(path).content.decode()


@pytest.mark.story("U11")
@pytest.mark.django_db
def test_admin_sets_url_and_link_appears(site_admin, player, club, login):
    admin = login(site_admin)
    assert admin.get(reverse("site_settings")).status_code == 200
    r = admin.post(reverse("site_settings"), {"donate_url": URL})
    assert r.status_code == 302
    assert SiteSettings.load().donate_url == URL
    member = login(player)
    for path in (reverse("home"), reverse("club_home", args=[club.slug])):
        html = body(member, path)
        assert f'href="{URL}"' in html
        assert 'target="_blank"' in html and 'rel="noopener"' in html
    assert f'href="{URL}"' in body(Client(), reverse("login"))


@pytest.mark.story("U11")
@pytest.mark.django_db
def test_clearing_hides_link(site_admin, player, club, login):
    admin = login(site_admin)
    admin.post(reverse("site_settings"), {"donate_url": URL})
    admin.post(reverse("site_settings"), {"donate_url": ""})
    assert SiteSettings.load().donate_url == ""
    member = login(player)
    for path in (reverse("home"), reverse("club_home", args=[club.slug])):
        assert 'class="donate"' not in body(member, path)
    assert 'class="donate"' not in body(Client(), reverse("login"))


@pytest.mark.story("U11")
@pytest.mark.django_db
def test_non_admins_forbidden(club_admin, player, login):
    for u in (club_admin, player):
        c = login(u)
        assert c.get(reverse("site_settings")).status_code == 403
        assert c.post(reverse("site_settings"), {"donate_url": URL}).status_code == 403
    assert Client().get(reverse("site_settings")).status_code == 302
    assert SiteSettings.load().donate_url == ""


@pytest.mark.story("U11")
@pytest.mark.django_db
def test_invalid_url_rejected(site_admin, login):
    r = login(site_admin).post(reverse("site_settings"), {"donate_url": "not a url"})
    assert r.status_code == 200
    assert SiteSettings.load().donate_url == ""
