import pytest
from django.http import HttpResponse
from django.urls import reverse

from accounts import permissions as p
from accounts.models import Club, Membership, User

pytestmark = pytest.mark.story("FOUNDATION")


def _status(login, user, club, view):
    # Decorators are exercised through real views: index views use club_member_required.
    return login(user).get(reverse("items:index", args=[club.slug])).status_code


def test_member_decorator(login, player, club_admin, game_master, site_admin, club):
    for u in (player, club_admin, game_master, site_admin):
        assert _status(login, u, club, None) == 200


def _call(decorator, user, club):
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    request.user = user
    request.club = club
    request.membership = Membership.objects.filter(user=user, club=club).first()
    return decorator(lambda r: HttpResponse("ok"))(request)


@pytest.mark.parametrize(
    "decorator,allowed",
    [
        (p.club_member_required, {"player", "game_master", "club_admin", "site_admin"}),
        (p.club_admin_required, {"club_admin", "site_admin"}),
        (p.game_master_required, {"game_master", "site_admin"}),
        (p.admin_or_gm_required, {"game_master", "club_admin", "site_admin"}),
    ],
)
def test_decorator_matrix(decorator, allowed, club, player, game_master, club_admin, site_admin):
    from django.core.exceptions import PermissionDenied

    users = {
        "player": player,
        "game_master": game_master,
        "club_admin": club_admin,
        "site_admin": site_admin,
    }
    for name, user in users.items():
        if name in allowed:
            assert _call(decorator, user, club).status_code == 200
        else:
            with pytest.raises(PermissionDenied):
                _call(decorator, user, club)


def test_non_member_decorator_refused(club, other_club, player):
    from django.core.exceptions import PermissionDenied

    outsider = User.objects.create_user("o@example.com", password="pw")
    with pytest.raises(PermissionDenied):
        _call(p.club_member_required, outsider, club)


def test_site_admin_required(rf, player, site_admin):
    from django.core.exceptions import PermissionDenied

    view = p.site_admin_required(lambda r: HttpResponse("ok"))
    req = rf.get("/")
    req.user = site_admin
    assert view(req).status_code == 200
    req.user = player
    with pytest.raises(PermissionDenied):
        view(req)


def test_can_view_inventory(character, player, other_player, game_master, club_admin, site_admin):
    assert p.can_view_inventory(player, character)
    assert p.can_view_inventory(game_master, character)
    assert p.can_view_inventory(club_admin, character)
    assert p.can_view_inventory(site_admin, character)
    assert not p.can_view_inventory(other_player, character)


def test_can_see_email(club, player, club_admin, game_master, site_admin):
    assert p.can_see_email(club_admin, club)
    assert p.can_see_email(site_admin, club)
    assert not p.can_see_email(player, club)
    assert not p.can_see_email(game_master, club)


def test_can_reset_password(club, other_club, club_admin, player, site_admin):
    assert p.can_reset_password(club_admin, player)
    assert p.can_reset_password(site_admin, player)
    assert not p.can_reset_password(player, club_admin)
    # target also belongs to a club the actor does not administer
    Membership.objects.create(user=player, club=other_club)
    assert not p.can_reset_password(club_admin, player)
    Membership.objects.create(user=club_admin, club=other_club, is_club_admin=True)
    assert p.can_reset_password(club_admin, player)
    # nobody but a site admin resets a site admin
    assert not p.can_reset_password(club_admin, site_admin)
    # a user in no club cannot be reset by a club admin
    loner = User.objects.create_user("l@example.com", password="pw")
    assert not p.can_reset_password(club_admin, loner)
    assert Club.objects.count() == 2
