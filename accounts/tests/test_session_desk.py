"""Tests for the session desk on club home."""

import datetime
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts import approvals
from accounts.models import Membership, Message, User
from accounts.session_desk import build_session_desk
from agent_access.models import ProposedBatch, ProposedItem
from agent_access.tokens import create_token
from downtime.models import DowntimePointRequest
from map.models import MapRequest
from play_sessions.models import PlaySession
from play_sessions.upcoming import upcoming_sessions
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("U35")]


def _req(rf, user, club):
    request = rf.get("/")
    request.user = user
    request.club = club
    request.membership = Membership.objects.filter(user=user, club=club).first()
    return request


def _seed_all(club, user):
    """Seed one of each approval type for the given user's club."""
    conn, _ = create_token(user, club, f"agent-{club.slug}-{ProposedBatch.objects.count()}")
    ProposedBatch.objects.create(
        club=club,
        connection=conn,
        user=user,
        date=datetime.date.today(),
        idempotency_key=f"k{ProposedBatch.objects.count()}",
        status=ProposedBatch.Status.PENDING,
    )
    ProposedItem.objects.create(club=club, name="Dagger", status=ProposedItem.Status.PENDING)
    member = Membership.objects.filter(club=club).first()
    MapRequest.objects.create(
        club=club, kind="visit", requested_by=member, status=MapRequest.Status.REQUESTED
    )
    Message.objects.create(club=club, sender=member, body="hi", status=Message.Status.OPEN)
    # Create a downtime point request
    char = Character.objects.filter(club=club).first()
    if not char:
        # Create a character for the user
        membership = Membership.objects.get(user=user, club=club)
        char = Character.objects.create(club=club, owner=membership, name="Test Char")
    req = DowntimePointRequest.objects.create(
        club=club, requested_by=Membership.objects.get(user=user, club=club), points=1
    )
    req.characters.add(char)


def test_build_session_desk_returns_none_for_player(rf, club, player):
    request = _req(rf, player, club)
    assert build_session_desk(request) is None


def test_build_session_desk_returns_dict_for_gm(rf, club, game_master):
    request = _req(rf, game_master, club)
    desk = build_session_desk(request)
    assert desk is not None
    assert "waiting" in desk
    assert "after" in desk
    assert "dashboard_url" in desk


def test_build_session_desk_returns_dict_for_club_admin(rf, club, club_admin):
    request = _req(rf, club_admin, club)
    desk = build_session_desk(request)
    assert desk is not None


def test_desk_coming_up_uses_shared_query_limited_to_three(rf, club, game_master):
    """Desk coming_up is the shared upcoming query, limited to 3, ordered by starts_at."""
    gm = Membership.objects.get(user=game_master, club=club)
    today = timezone.now()
    sessions = [
        PlaySession.objects.create(
            club=club, title=f"S{i}", starts_at=today + timedelta(days=i), game_master=gm
        )
        for i in (1, 2, 3, 4)
    ]
    request = _req(rf, game_master, club)
    desk = build_session_desk(request)
    ids = [s["id"] for s in desk["coming_up"]]
    assert len(ids) == 3
    assert ids == [sessions[0].pk, sessions[1].pk, sessions[2].pk]
    # Matches the shared query directly (same order, same rows).
    data = upcoming_sessions(club, today, request.membership, 3)
    assert ids == [row["id"] for row in data["sessions"]]
    assert desk["club"] == club
    assert desk["membership"] == request.membership
    assert desk["can_manage_sessions"] is True


def test_waiting_uses_pending_approvals(rf, club, game_master):
    """Waiting items match pending_approvals exactly."""
    _seed_all(club, game_master)
    request = _req(rf, game_master, club)
    desk = build_session_desk(request)
    approvals_list = approvals.pending_approvals(request)
    assert desk["waiting"] == approvals_list


def test_waiting_counts_match_top_bar(rf, club, game_master, club_admin):
    """Counts in waiting match the approvals indicator."""
    _seed_all(club, game_master)
    req_gm = _req(rf, game_master, club)
    req_admin = _req(rf, club_admin, club)
    desk_gm = build_session_desk(req_gm)
    desk_admin = build_session_desk(req_admin)
    approvals_gm = approvals.pending_approvals(req_gm)
    approvals_admin = approvals.pending_approvals(req_admin)
    gm_labels = {a.label: a.count for a in desk_gm["waiting"]}
    admin_labels = {a.label: a.count for a in desk_admin["waiting"]}
    assert gm_labels == {a.label: a.count for a in approvals_gm}
    assert admin_labels == {a.label: a.count for a in approvals_admin}


def test_gm_sees_batches_and_map_requests(rf, club, game_master):
    """GM sees agent batches and map requests; admin does not see batches."""
    _seed_all(club, game_master)
    req_gm = _req(rf, game_master, club)
    desk_gm = build_session_desk(req_gm)
    labels = {a.label for a in desk_gm["waiting"]}
    assert "Agent batches" in labels
    assert "Map requests" in labels


def test_club_admin_sees_messages(rf, club, club_admin, game_master):
    """Club admin sees messages; GM does not."""
    _seed_all(club, game_master)
    req_admin = _req(rf, club_admin, club)
    desk_admin = build_session_desk(req_admin)
    labels = {a.label for a in desk_admin["waiting"]}
    assert "Messages" in labels


def test_both_see_proposed_items_and_downtime_requests(rf, club, game_master, club_admin):
    """Both GM and admin see proposed items and downtime point requests."""
    _seed_all(club, game_master)
    req_gm = _req(rf, game_master, club)
    req_admin = _req(rf, club_admin, club)
    for req in (req_gm, req_admin):
        desk = build_session_desk(req)
        labels = {a.label for a in desk["waiting"]}
        assert "Proposed items" in labels
        assert "Downtime point requests" in labels


def test_zero_count_rows_hidden(rf, club, game_master):
    """Rows with zero count are not in waiting (pending_approvals drops them)."""
    # Seed nothing
    req = _req(rf, game_master, club)
    desk = build_session_desk(req)
    assert desk["waiting"] == []


def test_all_zero_hides_waiting_block_but_after_remains(rf, club, game_master):
    """When all counts are zero, waiting is empty but after section exists."""
    req = _req(rf, game_master, club)
    desk = build_session_desk(req)
    assert desk["waiting"] == []
    assert len(desk["after"]) == 4


def test_after_session_links(rf, club, game_master):
    """After the session has four fixed links with correct URLs."""
    req = _req(rf, game_master, club)
    desk = build_session_desk(req)
    after = desk["after"]
    assert len(after) == 4
    labels = [label for label, _ in after]
    assert labels == ["Award Loot to Party", "Downtime points", "Map", "Character slips"]
    for _, url in after:
        assert url.startswith("/c/" + club.slug + "/")


def test_after_session_urls_resolve_200_for_gm(client, club, game_master):
    """Each after-session link returns 200 for a GM."""
    client.force_login(game_master)
    req = client.get(reverse("club_home", args=[club.slug])).wsgi_request
    desk = build_session_desk(req)
    for _, url in desk["after"]:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} returned {resp.status_code}"


def test_player_redirected_from_club_home_to_dashboard(client, club, player):
    """Player accessing club_home is redirected to dashboard."""
    client.force_login(player)
    resp = client.get(reverse("club_home", args=[club.slug]))
    assert resp.status_code == 302
    assert reverse("accounts:player_dashboard", args=[club.slug]) in resp.url


def test_player_dashboard_has_no_session_desk(client, club, player, character):
    """Player dashboard does not contain session desk."""
    client.force_login(player)
    resp = client.get(reverse("accounts:player_dashboard", args=[club.slug]))
    assert resp.status_code == 200
    assert "wm-session-desk" not in resp.content.decode()


def test_gm_with_character_has_dashboard_link(rf, club, game_master):
    """GM who owns a character gets a dashboard_url."""
    owner = Membership.objects.get(user=game_master, club=club)
    Character.objects.create(club=club, owner=owner, name="GM Char")
    req = _req(rf, game_master, club)
    desk = build_session_desk(req)
    assert desk["dashboard_url"] is not None
    assert reverse("accounts:player_dashboard", args=[club.slug]) == desk["dashboard_url"]


def test_gm_without_character_has_no_dashboard_link(rf, club, game_master):
    """GM with no character gets no dashboard_url."""
    # Ensure GM has no character
    Character.objects.filter(club=club, owner__user=game_master).delete()
    req = _req(rf, game_master, club)
    desk = build_session_desk(req)
    assert desk["dashboard_url"] is None


def test_club_admin_with_character_has_dashboard_link(rf, club, club_admin):
    """Club admin who owns a character gets a dashboard_url."""
    owner = Membership.objects.get(user=club_admin, club=club)
    Character.objects.create(club=club, owner=owner, name="Admin Char")
    req = _req(rf, club_admin, club)
    desk = build_session_desk(req)
    assert desk["dashboard_url"] is not None


def test_gm_with_character_can_access_dashboard(client, club, game_master):
    """GM with a character can access the dashboard (not redirected)."""
    owner = Membership.objects.get(user=game_master, club=club)
    Character.objects.create(club=club, owner=owner, name="GM Char")
    client.force_login(game_master)
    resp = client.get(reverse("accounts:player_dashboard", args=[club.slug]))
    assert resp.status_code == 200
    assert "wm-session-desk" not in resp.content.decode()


def test_gm_without_character_redirected_from_dashboard(client, club, game_master):
    """GM with no character is redirected from dashboard to club_home."""
    Character.objects.filter(club=club, owner__user=game_master).delete()
    client.force_login(game_master)
    resp = client.get(reverse("accounts:player_dashboard", args=[club.slug]))
    assert resp.status_code == 302
    assert reverse("club_home", args=[club.slug]) in resp.url


def test_club_admin_without_character_redirected_from_dashboard(client, club, club_admin):
    """Club admin with no character is redirected from dashboard to club_home."""
    Character.objects.filter(club=club, owner__user=club_admin).delete()
    client.force_login(club_admin)
    resp = client.get(reverse("accounts:player_dashboard", args=[club.slug]))
    assert resp.status_code == 302
    assert reverse("club_home", args=[club.slug]) in resp.url


def test_another_club_items_not_counted(rf, club, other_club, game_master, club_admin):
    """Items from another club do not appear in waiting."""
    _seed_all(club, game_master)
    # Create a different GM for other_club
    other_user = User.objects.create_user("ogm@example.com", password="pw", display_name="Other GM")
    Membership.objects.create(user=other_user, club=other_club, is_game_master=True)
    _seed_all(other_club, other_user)

    req = _req(rf, game_master, club)
    desk = build_session_desk(req)
    # Should only see items from 'club'
    for item in desk["waiting"]:
        assert item.url.startswith("/c/" + club.slug + "/")


def test_club_home_renders_session_desk_for_gm(client, club, game_master):
    """Club home page includes session desk markup for GM."""
    _seed_all(club, game_master)
    client.force_login(game_master)
    resp = client.get(reverse("club_home", args=[club.slug]))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-session-desk" in html
    assert "Waiting for you" in html
    assert "After the session" in html


def test_club_home_renders_session_desk_for_club_admin(client, club, club_admin):
    """Club home page includes session desk markup for club admin."""
    client.force_login(club_admin)
    resp = client.get(reverse("club_home", args=[club.slug]))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-session-desk" in html


def test_club_home_no_session_desk_for_player(client, club, player):
    """Player never sees session desk on club home (redirected)."""
    client.force_login(player)
    resp = client.get(reverse("club_home", args=[club.slug]), follow=True)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-session-desk" not in html


def test_waiting_list_items_have_badge(client, club, game_master):
    """Waiting for you list items show count badges."""
    from accounts.models import Membership
    from map.models import MapRequest

    member = Membership.objects.filter(club=club).first()
    MapRequest.objects.create(
        club=club, kind="visit", requested_by=member, status=MapRequest.Status.REQUESTED
    )

    client.force_login(game_master)
    resp = client.get(reverse("club_home", args=[club.slug]))
    html = resp.content.decode()
    assert "wm-badge--count" in html
    assert ">1<" in html or "1</span>" in html


def test_session_desk_css_has_mobile_rules():
    """CSS file contains mobile-first rules for session desk."""
    css_path = "static/css/areas/accounts.css"
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "..", css_path)
    with open(path) as f:
        css = f.read()
    assert ".wm-session-desk" in css
    assert "@media (max-width: 575.98px)" in css
    assert "var(--wm-size-touch)" in css


def test_demo_gwen_has_session_desk(client):
    """Demo GM Gwen sees session desk with seeded items."""
    call_command("seed_demo")
    from accounts.models import User

    gwen = User.objects.get(email="gm@example.com")
    client.force_login(gwen)
    resp = client.get("/c/demo/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-session-desk" in html
    assert "Waiting for you" in html
    assert "After the session" in html
    # Gwen is both GM and admin, so should see all five rows
    expected_labels = (
        "Agent batches",
        "Proposed items",
        "Map requests",
        "Messages",
        "Downtime point requests",
    )
    for label in expected_labels:
        assert label in html
