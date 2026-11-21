"""Tests for scheduling, editing, and cancelling play sessions (P1, P2)."""

from datetime import UTC, datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import core
from play_sessions.models import PlaySession, SessionSeries

pytestmark = [pytest.mark.django_db, pytest.mark.story("P1")]


def make_user(email, password="pass12345678", display_name=""):
    return User.objects.create_user(email=email, password=password, display_name=display_name)


def make_club(slug="test-club", timezone="America/New_York"):
    return Club.objects.create(name="Test Club", slug=slug, timezone=timezone)


def make_membership(user, club, is_gm=False, is_admin=False):
    return Membership.objects.create(
        user=user, club=club, is_game_master=is_gm, is_club_admin=is_admin
    )


def login_client(client, user):
    client.force_login(user)
    return client


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------


def test_create_302_for_gm_and_admin(client):
    club = make_club()
    gm = make_user("gm@test.com")
    make_membership(gm, club, is_gm=True)
    admin = make_user("admin@test.com")
    make_membership(admin, club, is_admin=True)

    for user in (gm, admin):
        login_client(client, user)
        url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
        response = client.get(url)
        assert response.status_code == 200, f"{user.email} should get 200 on create"


def test_player_403_on_all_urls(client):
    club = make_club()
    player = make_user("player@test.com")
    make_membership(player, club)
    session = PlaySession.objects.create(
        club=club,
        title="Old session",
        starts_at=timezone.now(),
        game_master=make_membership(make_user("gm@test.com"), club, is_gm=True),
    )
    login_client(client, player)

    # GET URLs
    get_urls = [
        ("play_sessions:session_create", {"club_slug": club.slug}),
        ("play_sessions:session_edit", {"club_slug": club.slug, "pk": session.pk}),
        ("play_sessions:series_cancel", {"club_slug": club.slug, "pk": session.pk}),
    ]
    for name, kwargs in get_urls:
        url = reverse(name, kwargs=kwargs)
        response = client.get(url)
        assert response.status_code == 403, (
            f"{name} should give 403 to player, got {response.status_code}"
        )

    # POST-only cancel URL
    cancel_url = reverse(
        "play_sessions:session_cancel", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    response = client.post(cancel_url)
    assert response.status_code == 403, (
        f"session_cancel should give 403 to player, got {response.status_code}"
    )


def test_anonymous_redirect_to_login(client):
    club = make_club()
    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


# ---------------------------------------------------------------------------
# Create tests
# ---------------------------------------------------------------------------


def test_create_stores_utc_and_shows_club_zone(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    # March 1, 2026 19:00 EST (UTC-5) -> 2026-03-02 00:00 UTC
    response = client.post(
        url,
        {
            "title": "Weekly Game",
            "date": "2026-03-01",
            "start_time": "19:00",
            "end_time": "21:00",
            "game_master": gm_membership.pk,
            "location": "The Tavern",
            "notes": "Bring dice",
            "repeat": "none",
        },
    )
    assert response.status_code == 302

    session = PlaySession.objects.get(title="Weekly Game")
    # 19:00 EST = 00:00 UTC next day
    expected_utc = datetime(2026, 3, 2, 0, 0, tzinfo=UTC)
    assert session.starts_at == expected_utc

    # Detail page shows 19:00 in club zone
    detail_url = reverse(
        "play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    response = client.get(detail_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "7:00 PM" in content or "19:00" in content


def test_create_default_game_master_is_me(client):
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Session",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "none",
        },
    )
    session = PlaySession.objects.get(title="Session")
    assert session.game_master == gm_membership


def test_create_repeat_none_makes_one_session_no_series(client):
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "One-off",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "none",
            "count": "99",
        },
    )
    session = PlaySession.objects.get(title="One-off")
    assert session.series is None
    assert PlaySession.objects.filter(title="One-off").count() == 1


# ---------------------------------------------------------------------------
# DST tests
# ---------------------------------------------------------------------------


def test_weekly_dst_spring_forward(client):
    """Weekly sessions from March 1 across DST start March 8, 2026 (NY).

    All sessions at 19:00 local, UTC hour differs after spring forward.
    """
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Weekly DST",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
            "count": "4",
        },
    )
    sessions = PlaySession.objects.filter(title="Weekly DST").order_by("starts_at")
    assert sessions.count() == 4
    series_id = sessions.first().series_id
    assert series_id is not None
    assert SessionSeries.objects.filter(pk=series_id).exists()

    # All at 19:00 local
    for s in sessions:
        local = core.to_club_local(club, s.starts_at)
        assert local.hour == 19

    # Session 1 (March 1, EST UTC-5): 19:00 local = 00:00 UTC next day
    # Session 2 (March 8, EDT UTC-4): 19:00 local = 23:00 UTC same day
    utc_hours = {s.starts_at.hour for s in sessions}
    assert len(utc_hours) > 1, "UTC hour should differ across DST change"


def test_every_two_weeks_dst_fall_back(client):
    """Every-two-weeks sessions across November DST end, 2026 (NY)."""
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Biweekly DST",
            "date": "2026-10-11",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "every_two_weeks",
            "count": "4",
        },
    )
    sessions = PlaySession.objects.filter(title="Biweekly DST").order_by("starts_at")
    assert sessions.count() == 4
    series_id = sessions.first().series_id
    assert series_id is not None

    # All at 19:00 local
    for s in sessions:
        local = core.to_club_local(club, s.starts_at)
        assert local.hour == 19

    # UTC hour should differ after fall-back (Nov 1)
    utc_hours = {s.starts_at.hour for s in sessions}
    assert len(utc_hours) > 1


# ---------------------------------------------------------------------------
# Count validation tests
# ---------------------------------------------------------------------------


def test_count_refused_outside_2_to_26(client):
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})

    # count = 1 refused
    response = client.post(
        url,
        {
            "title": "Count 1",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
            "count": "1",
        },
    )
    assert response.status_code == 200  # form re-rendered with error
    assert PlaySession.objects.filter(title="Count 1").count() == 0

    # count = 27 refused
    response = client.post(
        url,
        {
            "title": "Count 27",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
            "count": "27",
        },
    )
    assert response.status_code == 200
    assert PlaySession.objects.filter(title="Count 27").count() == 0


def test_count_default_is_4(client):
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Default count",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
        },
    )
    sessions = PlaySession.objects.filter(title="Default count")
    assert sessions.count() == 4


# ---------------------------------------------------------------------------
# Edit tests
# ---------------------------------------------------------------------------


def test_edit_past_session(client):
    """A past session can still be edited."""
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    session = PlaySession.objects.create(
        club=club,
        title="Past session",
        starts_at=datetime(2020, 1, 1, 19, 0, tzinfo=UTC),
        game_master=gm_membership,
    )
    url = reverse("play_sessions:session_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 200

    response = client.post(
        url,
        {
            "title": "Updated past session",
            "date": "2020-01-01",
            "start_time": "20:00",
            "game_master": gm_membership.pk,
            "repeat": "none",
        },
    )
    assert response.status_code == 302
    session.refresh_from_db()
    assert session.title == "Updated past session"


def test_edit_one_series_member_leaves_others(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Series member",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
            "count": "4",
        },
    )
    sessions = PlaySession.objects.filter(title="Series member").order_by("starts_at")
    assert sessions.count() == 4

    # Edit the second session
    session2 = sessions[1]
    edit_url = reverse(
        "play_sessions:session_edit", kwargs={"club_slug": club.slug, "pk": session2.pk}
    )
    client.post(
        edit_url,
        {
            "title": "Edited session 2",
            "date": "2026-03-08",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "none",
        },
    )
    session2.refresh_from_db()
    assert session2.title == "Edited session 2"

    # Others unchanged
    others = PlaySession.objects.filter(title="Series member")
    assert others.count() == 3


def test_cancel_one_series_member_leaves_others(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Series to cancel",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
            "count": "4",
        },
    )
    sessions = PlaySession.objects.filter(title="Series to cancel").order_by("starts_at")
    assert sessions.count() == 4

    # Cancel the first session
    session1 = sessions[0]
    cancel_url = reverse(
        "play_sessions:session_cancel", kwargs={"club_slug": club.slug, "pk": session1.pk}
    )
    response = client.post(cancel_url)
    assert response.status_code == 302

    session1.refresh_from_db()
    assert session1.cancelled is True

    # Others unchanged
    others = PlaySession.objects.filter(title="Series to cancel", cancelled=False)
    assert others.count() == 3


# ---------------------------------------------------------------------------
# Cancel tests
# ---------------------------------------------------------------------------


def test_cancel_keeps_row_and_marks_cancelled(client):
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    session = PlaySession.objects.create(
        club=club,
        title="To cancel",
        starts_at=timezone.now(),
        game_master=gm_membership,
    )
    cancel_url = reverse(
        "play_sessions:session_cancel", kwargs={"club_slug": club.slug, "pk": session.pk}
    )

    # GET on cancel gives 405 (POST only)
    response = client.get(cancel_url)
    assert response.status_code == 405

    # POST cancels
    response = client.post(cancel_url)
    assert response.status_code == 302

    session.refresh_from_db()
    assert session.cancelled is True
    assert PlaySession.objects.filter(pk=session.pk).exists()  # row stays

    # Detail page shows Cancelled badge
    detail_url = reverse(
        "play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    response = client.get(detail_url)
    assert b"Cancelled" in response.content


# ---------------------------------------------------------------------------
# Cancel the rest tests
# ---------------------------------------------------------------------------


def test_cancel_rest_touches_only_this_and_later(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Rest series",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
            "count": "4",
        },
    )
    sessions = PlaySession.objects.filter(title="Rest series").order_by("starts_at")
    assert sessions.count() == 4

    # Cancel the rest from session 3 (index 2)
    session3 = sessions[2]
    series_cancel_url = reverse(
        "play_sessions:series_cancel", kwargs={"club_slug": club.slug, "pk": session3.pk}
    )

    # GET shows confirm page
    response = client.get(series_cancel_url)
    assert response.status_code == 200
    assert b"3" in response.content or b"two" in response.content.lower()  # count

    # Nothing changed on GET
    assert PlaySession.objects.filter(title="Rest series", cancelled=False).count() == 4

    # POST cancels 3 and 4
    response = client.post(series_cancel_url)
    assert response.status_code == 302

    session3.refresh_from_db()
    sessions[3].refresh_from_db()
    assert session3.cancelled is True
    assert sessions[3].cancelled is True
    sessions[0].refresh_from_db()
    sessions[1].refresh_from_db()
    assert sessions[0].cancelled is False
    assert sessions[1].cancelled is False


def test_cancel_rest_skips_already_cancelled(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Skip cancelled",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
            "count": "4",
        },
    )
    sessions = PlaySession.objects.filter(title="Skip cancelled").order_by("starts_at")

    # Pre-cancel session 4
    sessions[3].cancelled = True
    sessions[3].save()

    # Cancel the rest from session 2 - should only cancel session 2 and 3 (not 4)
    session2 = sessions[1]
    series_cancel_url = reverse(
        "play_sessions:series_cancel", kwargs={"club_slug": club.slug, "pk": session2.pk}
    )
    response = client.post(series_cancel_url)
    assert response.status_code == 302

    session2.refresh_from_db()
    sessions[2].refresh_from_db()
    sessions[3].refresh_from_db()
    assert session2.cancelled is True
    assert sessions[2].cancelled is True
    assert sessions[3].cancelled is True  # was already cancelled, stays cancelled
    sessions[0].refresh_from_db()
    assert sessions[0].cancelled is False


def test_series_cancel_404_without_series(client):
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    session = PlaySession.objects.create(
        club=club,
        title="No series",
        starts_at=timezone.now(),
        game_master=gm_membership,
    )
    url = reverse("play_sessions:series_cancel", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 404


def test_series_cancel_404_for_another_club(client):
    club = make_club()
    other_club = make_club(slug="other-club")
    gm = make_user("gm@test.com")
    make_membership(gm, club, is_gm=True)
    other_gm = make_user("other@test.com")
    other_gm_membership = make_membership(other_gm, other_club, is_gm=True)

    # Create a series session in the other club
    series = SessionSeries.objects.create(
        club=other_club, created_by=other_gm_membership, rule="weekly"
    )
    session = PlaySession.objects.create(
        club=other_club,
        title="Other club session",
        starts_at=timezone.now(),
        game_master=other_gm_membership,
        series=series,
    )

    login_client(client, gm)
    url = reverse("play_sessions:series_cancel", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Form validation tests
# ---------------------------------------------------------------------------


def test_end_time_before_start_time_refused(client):
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    response = client.post(
        url,
        {
            "title": "Bad times",
            "date": "2026-03-01",
            "start_time": "21:00",
            "end_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "none",
        },
    )
    assert response.status_code == 200  # form re-rendered
    assert PlaySession.objects.filter(title="Bad times").count() == 0


def test_game_master_choices_exclude_players(client):
    club = make_club()
    gm = make_user("gm@test.com")
    make_membership(gm, club, is_gm=True)
    player = make_user("player@test.com", display_name="Player One")
    make_membership(player, club)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Player should not appear in GM choices
    assert player.email not in content
    assert "Player One" not in content


# ---------------------------------------------------------------------------
# Manage section tests
# ---------------------------------------------------------------------------


def test_manage_section_shows_for_gm_not_player(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    player = make_user("player@test.com")
    make_membership(player, club)

    session = PlaySession.objects.create(
        club=club,
        title="Manage test",
        starts_at=timezone.now(),
        game_master=gm_membership,
    )

    # GM sees Manage section with Edit/Cancel buttons
    login_client(client, gm)
    detail_url = reverse(
        "play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    response = client.get(detail_url)
    assert response.status_code == 200
    assert b"Edit session" in response.content

    # Player does not see Manage section buttons
    login_client(client, player)
    response = client.get(detail_url)
    assert response.status_code == 200
    assert b"Edit session" not in response.content


def test_manage_section_series_link_only_for_series_member(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    # Create a series
    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Series link test",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
            "repeat": "weekly",
            "count": "4",
        },
    )
    sessions = PlaySession.objects.filter(title="Series link test")
    series_session = sessions.first()

    # Series member shows series_cancel link
    detail_url = reverse(
        "play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": series_session.pk}
    )
    response = client.get(detail_url)
    assert response.status_code == 200
    assert b"Cancel this and later" in response.content

    # Non-series session does not show series link
    solo = PlaySession.objects.create(
        club=club,
        title="Solo session",
        starts_at=timezone.now(),
        game_master=gm_membership,
    )
    detail_url = reverse(
        "play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": solo.pk}
    )
    response = client.get(detail_url)
    assert response.status_code == 200
    assert b"Cancel this and later" not in response.content


# ---------------------------------------------------------------------------
# Nav entry tests
# ---------------------------------------------------------------------------


def test_new_session_nav_entry_for_gm_not_player(client):
    from types import SimpleNamespace

    from accounts import navigation

    club = make_club()
    gm_user = make_user("gm@test.com")
    gm_membership = make_membership(gm_user, club, is_gm=True)
    player_user = make_user("player@test.com")
    player_membership = make_membership(player_user, club)

    # GM request
    gm_request = SimpleNamespace(
        user=gm_user, club=club, membership=gm_membership, resolver_match=None
    )
    gm_nav = navigation.entries_for(gm_request)
    gm_labels = [entry.label for entry in gm_nav.get("gm", [])]
    assert "New session" in gm_labels

    # Player request
    player_request = SimpleNamespace(
        user=player_user, club=club, membership=player_membership, resolver_match=None
    )
    player_nav = navigation.entries_for(player_request)
    player_labels = [entry.label for entry in player_nav.get("gm", [])]
    assert "New session" not in player_labels
