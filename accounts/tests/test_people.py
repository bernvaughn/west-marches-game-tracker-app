import pytest
from django.test import Client
from django.urls import reverse

from accounts import passwords
from accounts.models import Membership, User, WhitelistEntry
from player_characters.models import Character


def wl(club):
    return reverse("accounts:whitelist", args=[club.slug])


def idx(club):
    return reverse("accounts:index", args=[club.slug])


@pytest.fixture
def known_temp(monkeypatch):
    monkeypatch.setattr(passwords, "generate_temporary_password", lambda: "Temp-Pass-123")
    return "Temp-Pass-123"


@pytest.mark.story("U1")
def test_new_email_creates_user_membership_entry(club, club_admin, login):
    resp = login(club_admin).post(
        wl(club), {"email": "New@Example.com", "display_name": "Newbie", "is_game_master": "on"}
    )
    assert resp.status_code == 200
    user = User.objects.get(email="new@example.com")
    m = Membership.objects.get(user=user, club=club)
    assert m.is_game_master and not m.is_club_admin
    assert WhitelistEntry.objects.filter(club=club, email="new@example.com").exists()


@pytest.mark.story("U1")
def test_existing_user_from_other_club_only_added(club, club_admin, club_b_member, login):
    resp = login(club_admin).post(wl(club), {"email": club_b_member.email}, follow=True)
    assert User.objects.filter(email=club_b_member.email).count() == 1
    assert Membership.objects.filter(user=club_b_member).count() == 2
    club_b_member.refresh_from_db()
    assert club_b_member.check_password("pw")
    assert "temp-password" not in resp.content.decode()
    assert "already had an account" in resp.content.decode()


@pytest.mark.story("U1")
def test_already_member_changes_nothing(club, club_admin, player, login):
    resp = login(club_admin).post(
        wl(club), {"email": player.email, "character_name": "Ghost"}, follow=True
    )
    assert "already a member" in resp.content.decode()
    assert not Character.objects.filter(name="Ghost").exists()
    assert Membership.objects.filter(club=club).count() == 2
    assert "temp-password" not in resp.content.decode()


@pytest.mark.story("U1")
def test_character_name_creates_owned_character(club, club_admin, login):
    login(club_admin).post(wl(club), {"email": "n@example.com", "character_name": "Borin"})
    m = Membership.objects.get(user__email="n@example.com", club=club)
    c = Character.objects.get(name="Borin")
    assert c.club == club and c.owner == m


@pytest.mark.story("U20")
def test_temp_password_shown_once_and_works(club, club_admin, login, known_temp):
    client = login(club_admin)
    resp = client.post(wl(club), {"email": "n@example.com"})
    assert known_temp in resp.content.decode()
    assert "no-store" in resp["Cache-Control"]
    assert Client().login(username="n@example.com", password=known_temp)
    assert User.objects.get(email="n@example.com").must_change_password is True
    assert known_temp not in client.get(wl(club)).content.decode()


@pytest.mark.story("U17")
def test_player_sees_no_emails(club, club_admin, player, login):
    body = login(player).get(idx(club)).content.decode()
    assert "admin@example.com" not in body and "player@example.com" not in body
    assert "Admin" in body


@pytest.mark.story("U17")
def test_admins_see_emails(club, club_admin, player, site_admin, login):
    for u in (club_admin, site_admin):
        body = login(u).get(idx(club)).content.decode()
        assert "player@example.com" in body


@pytest.mark.story("U17")
def test_reset_link_only_for_admin(club, club_admin, player, login):
    m = Membership.objects.get(user=player, club=club)
    url = reverse("accounts:reset_password", args=[club.slug, m.id])
    assert url in login(club_admin).get(idx(club)).content.decode()
    assert url not in login(player).get(idx(club)).content.decode()


@pytest.mark.story("U12")
def test_other_club_member_gets_404(club, club_b_member, login):
    c = login(club_b_member)
    assert c.get(idx(club)).status_code == 404
    assert c.get(wl(club)).status_code == 404


@pytest.mark.story("U12")
def test_admin_cannot_whitelist_into_other_club(other_club, club_admin, login):
    resp = login(club_admin).post(wl(other_club), {"email": "x@example.com"})
    assert resp.status_code == 404
    assert not User.objects.filter(email="x@example.com").exists()
    assert not Membership.objects.filter(club=other_club).exists()


@pytest.mark.story("U1")
def test_player_forbidden_on_whitelist(club, player, login):
    c = login(player)
    assert c.get(wl(club)).status_code == 403
    assert c.post(wl(club), {"email": "x@example.com"}).status_code == 403
