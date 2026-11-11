import pytest
from django.template import Context, Template
from django.test import RequestFactory
from django.urls import resolve, reverse

from accounts.models import Membership, User, WhitelistEntry
from accounts.passwords import get_or_create_member, set_temporary_password

pytestmark = pytest.mark.django_db


def club_urls(club, membership_id):
    s = club.slug
    return {
        "index": reverse("accounts:index", args=[s]),
        "whitelist": reverse("accounts:whitelist", args=[s]),
        "reset": reverse("accounts:reset_password", args=[s, membership_id]),
        "message_new": reverse("accounts:message_new", args=[s]),
        "inbox": reverse("accounts:message_inbox", args=[s]),
        "status": reverse("accounts:message_status", args=[s, 1]),
    }


@pytest.mark.story("FOUNDATION")
def test_member_and_admin_access(club, player, club_admin, login):
    mid = Membership.objects.get(user=player, club=club).id
    u = club_urls(club, mid)
    c = login(player)
    assert c.get(u["index"]).status_code == 200
    assert c.get(u["message_new"]).status_code == 200
    for k in ("whitelist", "reset", "inbox"):
        assert c.get(u[k]).status_code == 403
    assert c.post(u["status"]).status_code == 403
    a = login(club_admin)
    for k in ("whitelist", "reset", "inbox"):
        assert a.get(u[k]).status_code == 200
    assert a.post(u["status"]).status_code == 200
    assert a.get(u["status"]).status_code == 405


@pytest.mark.story("FOUNDATION")
def test_site_routes(site_admin, club_admin, login):
    for name in ("site_clubs", "site_club_new", "site_settings"):
        url = reverse(name)
        assert login(site_admin).get(url).status_code == 200
        assert login(club_admin).get(url).status_code == 403


@pytest.mark.story("FOUNDATION")
def test_anonymous_redirects(client, club):
    assert client.get(reverse("accounts:whitelist", args=[club.slug])).status_code == 302
    assert client.get(reverse("site_clubs")).status_code == 302


@pytest.mark.story("FOUNDATION")
def test_other_club_member_gets_404(club, player, club_b_member, login):
    mid = Membership.objects.get(user=player, club=club).id
    c = login(club_b_member)
    for url in club_urls(club, mid).values():
        assert c.get(url).status_code == 404


@pytest.mark.story("FOUNDATION")
def test_password_change_is_ours_and_nav_renders(club, club_admin, site_admin, login):
    from accounts.views import passwords

    assert resolve(reverse("password_change")).func is passwords.password_change
    r = login(club_admin).get(reverse("club_home", args=[club.slug]))
    assert b"Whitelist" in r.content and b"Site settings" not in r.content
    r = login(site_admin).get(reverse("club_home", args=[club.slug]))
    assert b"Site settings" in r.content


@pytest.mark.story("U1")
def test_get_or_create_member_new(club):
    m, temp = get_or_create_member(club, "  New@Example.COM ", "New", is_game_master=True)
    assert m.is_game_master and not m.is_club_admin
    assert m.user.email == "new@example.com"
    assert m.user.check_password(temp) and m.user.must_change_password
    assert WhitelistEntry.objects.filter(club=club, email="new@example.com").exists()


@pytest.mark.story("U1")
def test_get_or_create_member_existing(club, other_club, club_b_member):
    m, temp = get_or_create_member(club, "BMEMBER@example.com")
    assert temp is None
    assert m.user == club_b_member and club_b_member.check_password("pw")
    assert User.objects.filter(email__iexact="bmember@example.com").count() == 1
    assert Membership.objects.filter(user=club_b_member).count() == 2


@pytest.mark.story("U21")
def test_set_temporary_password_signs_out(player, login):
    c = login(player)
    assert c.get("/").status_code == 200
    temp = set_temporary_password(player)
    player.refresh_from_db()
    assert player.must_change_password and player.check_password(temp)
    assert c.get("/").status_code == 302


@pytest.mark.story("U17")
def test_member_email_tag(club, player, club_admin, site_admin):
    tpl = Template("{% load accounts_tags %}[{% member_email target %}]")
    for viewer, expected in (
        (player, "[]"),
        (club_admin, "[player@example.com]"),
        (site_admin, "[player@example.com]"),
    ):
        req = RequestFactory().get("/")
        req.user, req.club = viewer, club
        assert tpl.render(Context({"request": req, "target": player})) == expected
