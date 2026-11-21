import json

import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import Membership, User
from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.models import Character


def idx(club):
    return reverse("accounts:index", args=[club.slug])


def mr(club, pk):
    return reverse("accounts:member_roles", args=[club.slug, pk])


def _mem(club, user):
    return Membership.objects.get(user=user, club=club)


def _trigger(resp):
    return json.loads(resp["HX-Trigger"])


@pytest.mark.story("U134")
def test_promote_player_to_club_admin(club, club_admin, player, login):
    m = _mem(club, player)
    resp = login(club_admin).post(mr(club, m.pk), {"is_club_admin": "on"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    trigger = _trigger(resp)
    assert trigger["appModalClose"] is True
    assert trigger["peopleChanged"] is True
    assert trigger["toast"]["message"] == f"Roles updated for {player.display_name}."
    assert trigger["toast"]["type"] == "success"
    m.refresh_from_db()
    assert m.is_club_admin and not m.is_game_master


@pytest.mark.story("U134")
def test_add_game_master_to_admin_holds_both(club, club_admin, login):
    m = _mem(club, club_admin)
    resp = login(club_admin).post(
        mr(club, m.pk),
        {"is_club_admin": "on", "is_game_master": "on"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    m.refresh_from_db()
    assert m.is_club_admin and m.is_game_master


@pytest.mark.story("U134")
def test_remove_game_master(club, club_admin, login):
    m = _mem(club, club_admin)
    m.is_game_master = True
    m.save()
    resp = login(club_admin).post(mr(club, m.pk), {"is_club_admin": "on"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    m.refresh_from_db()
    assert m.is_club_admin and not m.is_game_master


@pytest.mark.story("U134")
def test_remove_admin_when_another_admin_exists(club, club_admin, login):
    second = User.objects.create_user("second@example.com", password="pw", display_name="Second")
    Membership.objects.create(user=second, club=club, is_club_admin=True)
    m = _mem(club, club_admin)
    resp = login(club_admin).post(mr(club, m.pk), {}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    m.refresh_from_db()
    assert not m.is_club_admin and not m.is_game_master
    assert Membership.objects.filter(club=club, is_club_admin=True).count() == 1


@pytest.mark.story("U134")
def test_sole_admin_cannot_demote_self(club, club_admin, login):
    m = _mem(club, club_admin)
    assert Membership.objects.filter(club=club, is_club_admin=True).count() == 1
    resp = login(club_admin).post(mr(club, m.pk), {}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "This club needs at least one club admin" in resp.content.decode()
    m.refresh_from_db()
    assert m.is_club_admin
    assert Membership.objects.filter(club=club, is_club_admin=True).count() == 1


@pytest.mark.story("U134")
def test_sole_admin_keep_only_game_master_refused(club, club_admin, login):
    m = _mem(club, club_admin)
    m.is_game_master = True
    m.save()
    resp = login(club_admin).post(mr(club, m.pk), {"is_game_master": "on"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "This club needs at least one club admin" in resp.content.decode()
    m.refresh_from_db()
    assert m.is_club_admin and m.is_game_master


@pytest.mark.story("U134")
def test_site_admin_cannot_remove_last_admin(club, club_admin, site_admin, login):
    m = _mem(club, club_admin)
    assert Membership.objects.filter(club=club, is_club_admin=True).count() == 1
    resp = login(site_admin).post(mr(club, m.pk), {}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "This club needs at least one club admin" in resp.content.decode()
    m.refresh_from_db()
    assert m.is_club_admin


@pytest.mark.story("U134")
def test_admin_demotes_other_then_loses_access(club, club_admin, login):
    b = User.objects.create_user("b@example.com", password="pw", display_name="B")
    bm = Membership.objects.create(user=b, club=club, is_club_admin=True)
    a = _mem(club, club_admin)
    resp = login(club_admin).post(mr(club, bm.pk), {}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    bm.refresh_from_db()
    assert not bm.is_club_admin
    assert a.is_club_admin
    # B is now a player and is refused on the next call; A is still the only admin.
    c = Client()
    c.force_login(b)
    assert c.get(mr(club, bm.pk)).status_code == 403
    assert c.post(mr(club, bm.pk), {}).status_code == 403
    assert Membership.objects.filter(club=club, is_club_admin=True).count() == 1


@pytest.mark.story("U134")
def test_player_and_game_master_not_admin_refused(club, club_admin, game_master, player, login):
    target = _mem(club, player)
    for u in (player, game_master):
        c = login(u)
        assert c.get(mr(club, target.pk)).status_code == 403
        assert c.post(mr(club, target.pk), {"is_club_admin": "on"}).status_code == 403
    target.refresh_from_db()
    assert not target.is_club_admin and not target.is_game_master


@pytest.mark.story("U134")
def test_club_admin_isolated_from_other_club(club, other_club, club_admin, club_b_member, login):
    bm = Membership.objects.get(user=club_b_member, club=other_club)
    c = login(club_admin)
    # Via club A's URL, a club B member's pk is not found.
    assert c.get(mr(club, bm.pk)).status_code == 404
    assert c.post(mr(club, bm.pk), {"is_club_admin": "on"}).status_code == 404
    # club_admin joins club B as a plain member, so club B's URL resolves but they are not an admin.
    Membership.objects.create(user=club_admin, club=other_club)
    assert c.get(mr(other_club, bm.pk)).status_code == 403
    assert c.post(mr(other_club, bm.pk), {"is_club_admin": "on"}).status_code == 403
    bm.refresh_from_db()
    assert not bm.is_club_admin and not bm.is_game_master


@pytest.mark.story("U134")
def test_site_admin_can_change_roles_in_any_club(
    club, other_club, club_b_member, site_admin, login
):
    bm = Membership.objects.get(user=club_b_member, club=other_club)
    resp = login(site_admin).post(
        mr(other_club, bm.pk),
        {"is_club_admin": "on", "is_game_master": "on"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    bm.refresh_from_db()
    assert bm.is_club_admin and bm.is_game_master


@pytest.mark.story("U134")
def test_remove_game_master_leaves_characters_and_ledger(club, club_admin, game_master, login):
    gm_membership = _mem(club, game_master)
    character = Character.objects.create(club=club, owner=gm_membership, name="Ged")
    record(character, "award", [Line(coins=10)], note="reward", actor=club_admin)
    before_chars = Character.objects.filter(owner=gm_membership).count()
    before_ledger = LedgerEntry.objects.filter(character=character).count()

    resp = login(club_admin).post(mr(club, gm_membership.pk), {}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    gm_membership.refresh_from_db()
    assert not gm_membership.is_game_master and not gm_membership.is_club_admin
    assert Character.objects.filter(owner=gm_membership).count() == before_chars
    assert LedgerEntry.objects.filter(character=character).count() == before_ledger
    # The actor stays logged in: the People page still loads.
    assert login(club_admin).get(idx(club)).status_code == 200


@pytest.mark.story("U134")
def test_people_page_shows_roles_to_admins_only(club, club_admin, game_master, player, login):
    body = login(club_admin).get(idx(club)).content.decode()
    assert 'id="people-list"' in body
    assert 'hx-disinherit="*"' in body
    # A player row shows the Roles icon button to an admin.
    player_m = _mem(club, player)
    assert reverse("accounts:member_roles", args=[club.slug, player_m.pk]) in body
    assert "person-gear" in body
    # Players and game masters do not see the Roles action.
    assert (
        reverse("accounts:member_roles", args=[club.slug, player_m.pk])
        not in login(player).get(idx(club)).content.decode()
    )
    gm_m = _mem(club, game_master)
    assert (
        reverse("accounts:member_roles", args=[club.slug, gm_m.pk])
        not in login(game_master).get(idx(club)).content.decode()
    )


@pytest.mark.story("U134")
def test_roles_link_shows_when_cannot_reset(club, other_club, club_admin, player, login):
    # The player is also a member of club B, which club_admin does not administer,
    # so the admin cannot reset the player's password but can still open Roles.
    Membership.objects.create(user=player, club=other_club)
    player_m = _mem(club, player)
    body = login(club_admin).get(idx(club)).content.decode()
    assert reverse("accounts:member_roles", args=[club.slug, player_m.pk]) in body
    assert reverse("accounts:reset_password", args=[club.slug, player_m.pk]) not in body


@pytest.mark.story("U134")
def test_roles_modal_get_returns_fragment(club, club_admin, player, login):
    m = _mem(club, player)
    resp = login(club_admin).get(mr(club, m.pk), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "<html" not in content
    assert "is_club_admin" in content
    assert "is_game_master" in content


@pytest.mark.story("U134")
def test_non_htmx_success_redirects(club, club_admin, player, login):
    m = _mem(club, player)
    resp = login(club_admin).post(mr(club, m.pk), {"is_club_admin": "on"})
    assert resp.status_code == 302
    assert resp.url == idx(club)
    m.refresh_from_db()
    assert m.is_club_admin
