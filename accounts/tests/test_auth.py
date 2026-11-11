import pytest
from django.urls import reverse

pytestmark = pytest.mark.story("FOUNDATION")


def test_login_with_email(client, player):
    resp = client.post(reverse("login"), {"username": "player@example.com", "password": "pw"})
    assert resp.status_code == 302
    assert resp["Location"] == reverse("home")
    assert client.get(reverse("home")).status_code == 200


def test_login_bad_password(client, player):
    resp = client.post(reverse("login"), {"username": "player@example.com", "password": "x"})
    assert resp.status_code == 200


def test_logout_post(login, player):
    client = login(player)
    assert client.get(reverse("logout")).status_code == 405
    resp = client.post(reverse("logout"))
    assert resp.status_code == 200
    assert b"logged out" in resp.content.lower()
    assert client.get(reverse("home")).status_code == 302


def test_home_lists_only_own_clubs(login, player, club, other_club):
    body = login(player).get(reverse("home")).content.decode()
    assert club.name in body
    assert other_club.name not in body


def test_home_lists_all_clubs_for_site_admin(login, site_admin, club, other_club):
    body = login(site_admin).get(reverse("home")).content.decode()
    assert club.name in body and other_club.name in body


def test_home_requires_login(client):
    assert client.get(reverse("home")).status_code == 302
