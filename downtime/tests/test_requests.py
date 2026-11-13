import pytest
from django.urls import reverse

from accounts.approvals import pending_approvals
from accounts.models import Membership
from downtime import services
from downtime.approvals import pending_point_requests
from downtime.models import DowntimePointEntry, DowntimePointRequest
from player_characters.models import Character

pytestmark = pytest.mark.story("D4")


def _url(name, club, *args):
    return reverse(f"downtime:{name}", args=[club.slug, *args])


@pytest.fixture
def other_character(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Bo")


def _post(client, club, chars, points=2, note="Great session"):
    return client.post(
        _url("request_new", club),
        {"characters": [c.pk for c in chars], "points": points, "note": note},
    )


def test_player_requests_for_own_character(login, club, player, character):
    resp = _post(login(player), club, [character])
    assert resp.status_code == 302
    req = DowntimePointRequest.objects.get()
    assert req.status == "pending"
    assert req.points == 2 and req.note == "Great session"
    assert list(req.characters.all()) == [character]


def test_note_required(login, club, player, character):
    resp = _post(login(player), club, [character], note="")
    assert resp.status_code == 200
    assert not DowntimePointRequest.objects.exists()


def test_cannot_request_for_others(
    login, club, player, character, other_character, other_club_character
):
    for c in (other_character, other_club_character):
        resp = _post(login(player), club, [c])
        assert resp.status_code == 200
    assert not DowntimePointRequest.objects.exists()


def test_gm_approves_awards(login, club, game_master, character, point_request):
    point_request.points = 3
    point_request.save()
    resp = login(game_master).post(_url("request_approve", club, point_request.pk))
    assert resp.status_code == 302
    point_request.refresh_from_db()
    assert point_request.status == "approved"
    assert point_request.decided_at and point_request.decided_by.user == game_master
    assert services.balance(character) == 3
    entry = DowntimePointEntry.objects.get()
    assert entry.kind == "request" and entry.source == f"request:{point_request.pk}"


def test_admin_approves(login, club, club_admin, character, point_request):
    login(club_admin).post(_url("request_approve", club, point_request.pk))
    assert services.balance(character) == 1


def test_decline_awards_nothing(login, club, game_master, character, point_request):
    login(game_master).post(_url("request_decline", club, point_request.pk))
    point_request.refresh_from_db()
    assert point_request.status == "declined"
    assert not DowntimePointEntry.objects.exists()


def test_second_decision_does_nothing(login, club, game_master, character, point_request):
    c = login(game_master)
    c.post(_url("request_approve", club, point_request.pk))
    c.post(_url("request_approve", club, point_request.pk))
    c.post(_url("request_decline", club, point_request.pk))
    point_request.refresh_from_db()
    assert point_request.status == "approved"
    assert services.balance(character) == 1


def test_player_cannot_decide(login, club, player, character, point_request):
    c = login(player)
    assert c.post(_url("request_approve", club, point_request.pk)).status_code == 403
    assert c.post(_url("request_decline", club, point_request.pk)).status_code == 403
    assert login(player).get(_url("request_approve", club, point_request.pk)).status_code in (
        403,
        405,
    )


def test_get_approve_not_allowed(login, club, game_master, point_request):
    assert (
        login(game_master).get(_url("request_approve", club, point_request.pk)).status_code == 405
    )


def test_queue_visibility(login, club, player, other_player, game_master, character, point_request):
    other_owner = Membership.objects.get(user=other_player, club=club)
    other_char = Character.objects.create(club=club, owner=other_owner, name="Bo")
    mine = point_request
    theirs = DowntimePointRequest.objects.create(club=club, requested_by=other_owner, points=5)
    theirs.characters.add(other_char)
    got = login(player).get(_url("requests", club)).context["requests"]
    assert got == [mine]
    got = login(game_master).get(_url("requests", club)).context["requests"]
    assert set(got) == {mine, theirs}


def test_approvals_indicator(rf, club, other_club, game_master, club_admin, player, point_request):
    def req_for(user, c=club):
        r = rf.get("/")
        r.user, r.club = user, c
        r.membership = Membership.objects.filter(user=user, club=c).first()
        return r

    assert pending_point_requests(req_for(game_master))[1] == 1
    assert pending_point_requests(req_for(club_admin))[1] == 1
    assert pending_point_requests(req_for(player)) is None
    point_request.status = "approved"
    point_request.save()
    assert pending_point_requests(req_for(game_master))[1] == 0
    assert pending_approvals


def test_cross_club_isolation(
    login, club, other_club, game_master, other_club_character, point_request
):
    owner = other_club_character.owner
    foreign = DowntimePointRequest.objects.create(club=other_club, requested_by=owner, points=1)
    foreign.characters.add(other_club_character)
    got = login(game_master).get(_url("requests", club)).context["requests"]
    assert got == [point_request]
    assert login(game_master).post(_url("request_approve", club, foreign.pk)).status_code == 404
    foreign.refresh_from_db()
    assert foreign.status == "pending"


def test_anonymous_redirects(client, club):
    assert client.get(_url("requests", club)).status_code == 302
    assert client.get(_url("request_new", club)).status_code == 302
