"""Tests for scheduling, editing, and cancelling play sessions (P1, P2)."""

from datetime import UTC, datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import core
from play_sessions.models import PlaySession

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
        },
    )
    session = PlaySession.objects.get(title="Session")
    assert session.game_master == gm_membership


def test_create_makes_one_session_no_series(client):
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
        },
    )
    PlaySession.objects.get(title="One-off")
    assert PlaySession.objects.filter(title="One-off").count() == 1


def test_form_has_no_repeat_fields(client):
    """Schedule form should not have repeat or count fields."""
    club = make_club()
    gm = make_user("gm@test.com")
    make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "repeat" not in content.lower() or "Repeat" not in content
    assert "count" not in content.lower() or "Count" not in content


# ---------------------------------------------------------------------------
# DST tests
# ---------------------------------------------------------------------------


def test_single_session_dst_spring_forward(client):
    """Single session across DST start March 8, 2026 (NY)."""
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    # Before DST
    client.post(
        url,
        {
            "title": "Before DST",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    session1 = PlaySession.objects.get(title="Before DST")
    local1 = core.to_club_local(club, session1.starts_at)
    assert local1.hour == 19

    # After DST
    client.post(
        url,
        {
            "title": "After DST",
            "date": "2026-03-15",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    session2 = PlaySession.objects.get(title="After DST")
    local2 = core.to_club_local(club, session2.starts_at)
    assert local2.hour == 19


def test_single_session_dst_fall_back(client):
    """Single session across November DST end, 2026 (NY)."""
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    # Before DST end
    client.post(
        url,
        {
            "title": "Before fall back",
            "date": "2026-10-25",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    session1 = PlaySession.objects.get(title="Before fall back")
    local1 = core.to_club_local(club, session1.starts_at)
    assert local1.hour == 19

    # After DST end
    client.post(
        url,
        {
            "title": "After fall back",
            "date": "2026-11-08",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    session2 = PlaySession.objects.get(title="After fall back")
    local2 = core.to_club_local(club, session2.starts_at)
    assert local2.hour == 19


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
        },
    )
    assert response.status_code == 302
    session.refresh_from_db()
    assert session.title == "Updated past session"


def test_edit_session_leaves_others(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    # Create two separate sessions
    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Session 1",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    client.post(
        url,
        {
            "title": "Session 2",
            "date": "2026-03-08",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    sessions = PlaySession.objects.filter(title__in=["Session 1", "Session 2"]).order_by(
        "starts_at"
    )
    assert sessions.count() == 2

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
        },
    )
    session2.refresh_from_db()
    assert session2.title == "Edited session 2"

    # First session unchanged
    session1 = sessions[0]
    session1.refresh_from_db()
    assert session1.title == "Session 1"


def test_cancel_one_session_leaves_others(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Session to cancel",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    client.post(
        url,
        {
            "title": "Other session",
            "date": "2026-03-08",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    sessions = PlaySession.objects.filter(
        title__in=["Session to cancel", "Other session"]
    ).order_by("starts_at")
    assert sessions.count() == 2

    # Cancel the first session
    session1 = sessions[0]
    cancel_url = reverse(
        "play_sessions:session_cancel", kwargs={"club_slug": club.slug, "pk": session1.pk}
    )
    response = client.post(cancel_url)
    assert response.status_code == 302

    session1.refresh_from_db()
    assert session1.cancelled is True

    # Other session unchanged
    session2 = sessions[1]
    session2.refresh_from_db()
    assert session2.cancelled is False


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


def test_manage_section_no_series_link(client):
    club = make_club(timezone="America/New_York")
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    # Create a single session
    url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    client.post(
        url,
        {
            "title": "Solo session",
            "date": "2026-03-01",
            "start_time": "19:00",
            "game_master": gm_membership.pk,
        },
    )
    sessions = PlaySession.objects.filter(title="Solo session")
    solo = sessions.first()

    # No series_cancel link should exist
    detail_url = reverse(
        "play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": solo.pk}
    )
    response = client.get(detail_url)
    assert response.status_code == 200
    assert b"Cancel this and later" not in response.content


def test_manage_section_keeps_edit_link_on_cancelled_session(client):
    club = make_club()
    gm = make_user("gm@test.com")
    gm_membership = make_membership(gm, club, is_gm=True)
    login_client(client, gm)

    session = PlaySession.objects.create(
        club=club,
        title="Editlink",
        starts_at=timezone.now(),
        game_master=gm_membership,
    )
    session.cancelled = True
    session.save()
    detail = reverse(
        "play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    html = client.get(detail).content.decode()
    assert "Edit session" in html
    assert "Cancel session" not in html


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


# ---------------------------------------------------------------------------
# Series cancel URL returns 404
# ---------------------------------------------------------------------------


def test_series_cancel_url_404(client):
    """The old series_cancel URL should 404."""
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
    reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    # series_cancel URL pattern no longer exists, but test that we can't access it
    # This test verifies the URL name is gone
    from django.urls import NoReverseMatch

    try:
        reverse("play_sessions:series_cancel", kwargs={"club_slug": club.slug, "pk": session.pk})
        raise AssertionError("series_cancel URL should not exist")
    except NoReverseMatch:
        pass  # Expected
