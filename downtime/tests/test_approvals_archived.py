"""Tests for archived character markers on downtime approval queues (U146)."""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.approvals import pending_approvals
from accounts.models import Membership
from downtime.approvals import pending_point_requests
from downtime.models import DowntimePointEntry, DowntimePointRequest
from player_characters.models import Character

pytestmark = pytest.mark.story("D4")


def _url(name, club, *args):
    return reverse(f"downtime:{name}", args=[club.slug, *args])


def _archive(character):
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])


def test_queue_shows_archived_for_pending_downtime_request(
    login, club, game_master, character, point_request
):
    """A pending downtime request from an archived character shows "Archived" on the queue."""
    _archive(character)

    page = login(game_master).get(_url("requests", club)).content.decode()
    assert "Archived" in page
    assert point_request.note in page


def test_queue_shows_archived_for_requesting_player(login, club, player, character, point_request):
    """The requesting player also sees the "Archived" marker on their own queue."""
    _archive(character)

    page = login(player).get(_url("requests", club)).content.decode()
    assert "Archived" in page


def test_queue_shows_living_character_without_marker(
    login, club, game_master, character, point_request
):
    """A living character shows no "Archived" marker on the queue."""
    page = login(game_master).get(_url("requests", club)).content.decode()
    assert ">Archived<" not in page


def test_gm_can_approve_archived_character_request(
    login, club, game_master, character, point_request
):
    """GM can still approve a pending request from an archived character; points are awarded."""
    _archive(character)
    point_request.points = 3
    point_request.save()

    resp = login(game_master).post(_url("request_approve", club, point_request.pk))
    assert resp.status_code == 302

    point_request.refresh_from_db()
    assert point_request.status == "approved"
    assert DowntimePointEntry.objects.filter(kind="request").exists()


def test_gm_can_decline_archived_character_request(
    login, club, game_master, character, point_request
):
    """GM can still decline a pending request from an archived character."""
    _archive(character)

    resp = login(game_master).post(_url("request_decline", club, point_request.pk))
    assert resp.status_code == 302

    point_request.refresh_from_db()
    assert point_request.status == "declined"


def test_nav_count_includes_archived_request(rf, club, game_master, point_request):
    """The navbar pending_point_requests count still includes requests from archived characters."""
    char = point_request.characters.first()
    _archive(char)

    def req_for(user):
        r = rf.get("/")
        r.user, r.club = user, club
        r.membership = user.memberships.filter(club=club).first()
        return r

    assert pending_point_requests(req_for(game_master))[1] == 1


def test_pending_approvals_total_includes_archived(rf, club, game_master, point_request):
    """The pending_approvals total still includes requests from archived characters."""
    char = point_request.characters.first()
    _archive(char)

    def req_for(user):
        r = rf.get("/")
        r.user, r.club = user, club
        r.membership = user.memberships.filter(club=club).first()
        return r

    total = sum(i.count for i in pending_approvals(req_for(game_master)))
    assert total >= 1


def test_queue_mixed_living_and_archived_character(
    login, club, game_master, player, character, point_request
):
    """A request with one living and one archived character shows the
    marker for the archived one."""
    owner = character.owner
    archived_char = Character.objects.create(
        club=club, owner=owner, name="Archived Char", archived_at=timezone.now()
    )
    requester = Membership.objects.get(user=player, club=club)
    req = DowntimePointRequest.objects.create(club=club, requested_by=requester, points=2)
    req.characters.add(character, archived_char)

    page = login(game_master).get(_url("requests", club)).content.decode()
    assert "Archived" in page
    assert character.name in page
    assert archived_char.name in page
