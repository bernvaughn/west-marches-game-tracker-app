import pytest
from django.urls import reverse

from accounts.models import Club, Membership, User
from map.models import XPLevel
from map.xp import DEFAULT_XP_TABLE

pytestmark = pytest.mark.django_db

NEW = "site_club_new"
LIST = "site_clubs"


def _post(client, **over):
    data = {
        "name": "Club C",
        "slug": "",
        "admin_email": "Boss@Example.com",
        "admin_display_name": "Boss",
    }
    data.update(over)
    return client.post(reverse(NEW), data)


@pytest.mark.story("U12")
def test_create_club_new_admin(site_admin, login):
    c = login(site_admin)
    r = _post(c)
    assert r.status_code == 200
    club = Club.objects.get(slug="club-c")
    assert XPLevel.objects.filter(club=club).count() == len(DEFAULT_XP_TABLE)
    user = User.objects.get(email="boss@example.com")
    assert Membership.objects.get(user=user, club=club).is_club_admin
    assert user.must_change_password
    assert "no-store" in r["Cache-Control"]
    pw = r.context["temp_password"]
    assert pw in r.content.decode()
    assert pw not in c.get(reverse(LIST)).content.decode()
    # U20: the new admin must change the temporary password first.
    r = login(user).get(reverse("club_home", args=["club-c"]))
    assert r.status_code == 302 and r.url == reverse("password_change")


@pytest.mark.story("U12")
def test_slug_blank_and_duplicate(site_admin, login, club):
    c = login(site_admin)
    _post(c, name="My New Club")
    assert Club.objects.filter(slug="my-new-club").exists()
    before = Club.objects.count()
    r = _post(c, name="Other", slug="club-a")
    assert r.status_code == 200
    assert "slug" in r.context["form"].errors
    assert Club.objects.count() == before


@pytest.mark.story("U12")
def test_existing_user_keeps_password(site_admin, login, player):
    r = _post(login(site_admin), admin_email=player.email)
    club = Club.objects.get(slug="club-c")
    player.refresh_from_db()
    assert player.check_password("pw")
    assert Membership.objects.get(user=player, club=club).is_club_admin
    assert "temp_password" not in r.context
    assert "Their password is unchanged" in r.content.decode()


@pytest.mark.story("U12")
def test_list_shows_counts_and_links(site_admin, login, club, player):
    body = login(site_admin).get(reverse(LIST)).content.decode()
    assert reverse("club_home", args=["club-a"]) in body
    assert "1 member" in body


@pytest.mark.story("U12")
@pytest.mark.parametrize("who", ["club_admin", "player"])
def test_non_site_admin_403(who, request, login):
    c = login(request.getfixturevalue(who))
    assert c.get(reverse(LIST)).status_code == 403
    assert c.get(reverse(NEW)).status_code == 403
    assert _post(c).status_code == 403
    assert not Club.objects.filter(slug="club-c").exists()


@pytest.mark.story("U12")
def test_switcher_member_sees_only_own_club(player, login, club, other_club):
    c = login(player)
    body = c.get(reverse("club_home", args=["club-a"])).content.decode()
    assert reverse("club_home", args=["club-a"]) in body
    assert reverse("club_home", args=["club-b"]) not in body
    assert c.get(reverse("club_home", args=["club-b"])).status_code == 404


@pytest.mark.story("U12")
def test_switcher_site_admin_sees_all(site_admin, login, club, other_club):
    body = login(site_admin).get(reverse("club_home", args=["club-a"])).content.decode()
    assert reverse("club_home", args=["club-a"]) in body
    assert reverse("club_home", args=["club-b"]) in body
