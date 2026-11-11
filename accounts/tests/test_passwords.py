import pytest
from django.contrib.auth import authenticate
from django.test import Client
from django.urls import reverse

from accounts.models import Membership

NEW_PW = "Tr1cky-Horse-Battery"


def _flag(user):
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    user.refresh_from_db()


def _change(client, old="pw", new=NEW_PW):
    return client.post(
        reverse("password_change"),
        {"old_password": old, "new_password1": new, "new_password2": new},
    )


def _reset_url(club, user):
    m = Membership.objects.get(club=club, user=user)
    return reverse("accounts:reset_password", args=[club.slug, m.pk])


@pytest.mark.story("U20")
def test_flagged_user_redirected_everywhere(club, player, login):
    _flag(player)
    client = login(player)
    change = reverse("password_change")
    for url in [
        "/",
        reverse("club_home", args=[club.slug]),
        reverse("accounts:index", args=[club.slug]),
        "/c/club-a/items/",
    ]:
        r = client.get(url)
        assert r.status_code == 302 and r.url == change, url
    assert client.get(change).status_code == 200
    static = client.get("/static/css/app.css")
    assert static.status_code != 302 or static.url != change


@pytest.mark.story("U20")
def test_flagged_user_can_log_out(player, login):
    _flag(player)
    client = login(player)
    client.post(reverse("logout"))
    assert "/login" in client.get("/").url


@pytest.mark.story("U20")
def test_change_clears_flag_and_unlocks(club, player, login):
    _flag(player)
    client = login(player)
    r = _change(client)
    assert r.status_code == 302
    player.refresh_from_db()
    assert player.must_change_password is False
    assert client.get(reverse("club_home", args=[club.slug])).status_code == 200


@pytest.mark.story("U22")
def test_change_own_password_stays_signed_in(player):
    client = Client()
    assert client.login(email=player.email, password="pw")
    assert _change(client).status_code == 302
    assert client.get("/").status_code == 200
    assert authenticate(email=player.email, password="pw") is None
    assert authenticate(email=player.email, password=NEW_PW) is not None


@pytest.mark.story("U21")
def test_admin_resets_member(club, club_admin, player, login):
    target_client = login(player)
    assert target_client.get("/").status_code == 200
    client = login(club_admin)
    url = _reset_url(club, player)
    assert client.get(url).status_code == 200
    r = client.post(url)
    assert r.status_code == 200
    assert "no-store" in r["Cache-Control"]
    player.refresh_from_db()
    assert player.must_change_password is True
    temp = r.context["temp_password"]
    assert temp in r.content.decode()
    assert player.check_password(temp)
    assert temp not in client.get(url).content.decode()
    assert target_client.get("/").status_code == 302


@pytest.mark.story("U21")
def test_admin_of_only_one_club_gets_403(club, other_club, club_admin, player, login):
    Membership.objects.create(user=player, club=other_club)
    client = login(club_admin)
    url = _reset_url(club, player)
    assert client.get(url).status_code == 403
    assert client.post(url).status_code == 403
    player.refresh_from_db()
    assert player.must_change_password is False


@pytest.mark.story("U21")
def test_only_site_admin_resets_site_admin(club, club_admin, site_admin, login):
    Membership.objects.create(user=site_admin, club=club)
    url = _reset_url(club, site_admin)
    assert login(club_admin).post(url).status_code == 403
    site_admin.refresh_from_db()
    assert site_admin.must_change_password is False


@pytest.mark.story("U21")
def test_site_admin_resets_club_admin(club, club_admin, site_admin, login):
    r = login(site_admin).post(_reset_url(club, club_admin))
    assert r.status_code == 200
    club_admin.refresh_from_db()
    assert club_admin.must_change_password is True


@pytest.mark.story("U12")
def test_cross_club_reset_is_404(
    club, other_club, club_admin, club_b_admin, player, club_b_member, login
):
    a_url = _reset_url(club, player)
    b_url = _reset_url(other_club, club_b_member)
    b_client = login(club_b_admin)
    assert b_client.get(a_url).status_code == 404
    assert b_client.post(a_url).status_code == 404
    m_b = Membership.objects.get(club=other_club, user=club_b_member)
    crossed = reverse("accounts:reset_password", args=[club.slug, m_b.pk])
    assert login(club_admin).get(crossed).status_code == 404
    assert b_url
