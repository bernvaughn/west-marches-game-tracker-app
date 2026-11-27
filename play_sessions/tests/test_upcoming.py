"""Tests for the shared upcoming-sessions query (play_sessions/upcoming.py).

``now`` is always a fixed, aware UTC datetime so the club-local "today"
boundary is deterministic, including for zones on the far side of UTC
midnight (America/New_York: local midnight is 04:00-05:00 UTC).
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions.models import PlayerRSVP, PlaySession
from play_sessions.upcoming import upcoming_sessions

pytestmark = [pytest.mark.django_db, pytest.mark.story("P18")]

_NY = ZoneInfo("America/New_York")


def _club(timezone_name="America/New_York", slug="club", name="Club"):
    return Club.objects.create(name=name, slug=slug, timezone=timezone_name)


def _membership(club, email, **flags):
    user = User.objects.create_user(email=email, password="pass12345678")
    return Membership.objects.create(user=user, club=club, **flags)


def _session(club, starts_at, ends_at=None, title="Session", cancelled=False, gm=None):
    return PlaySession.objects.create(
        club=club,
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        cancelled=cancelled,
        game_master=gm,
    )


def _ny(date_obj, hour, minute=0):
    """Aware UTC datetime for the given America/New_York local wall time on a date."""
    return datetime(
        date_obj.year, date_obj.month, date_obj.day, hour, minute, tzinfo=_NY
    ).astimezone(UTC)


def test_today_or_later_filter_starts_or_ends():
    club = _club()
    today = datetime(2024, 7, 15).date()
    now = _ny(today, 10)  # 10:00 EDT
    gm = _membership(club, "gm@test.com", is_game_master=True)

    ended_today = _session(
        club,
        starts_at=_ny(today - timedelta(days=1), 23),  # 23:00 EDT previous day
        ends_at=_ny(today, 1),  # 01:00 EDT today
        title="Started yesterday, ends today",
        gm=gm,
    )
    starts_today = _session(
        club,
        starts_at=_ny(today, 15),
        ends_at=_ny(today, 18),
        title="Starts today",
        gm=gm,
    )
    starts_tomorrow = _session(
        club,
        starts_at=_ny(today + timedelta(days=1), 10),
        title="Starts tomorrow",
        gm=gm,
    )
    _session(
        club,
        starts_at=_ny(today - timedelta(days=1), 20),
        ends_at=_ny(today - timedelta(days=1), 23),
        title="Yesterday only",
        gm=gm,
    )  # excluded

    result = upcoming_sessions(club, now, None, 10)
    ids = [s["id"] for s in result["sessions"]]
    assert ids == [ended_today.pk, starts_today.pk, starts_tomorrow.pk]


def test_seven_pm_session_listed_at_eleven_pm_dropped_after_midnight():
    # Fixed clock, club zone on the far side of UTC midnight (America/New_York).
    club = _club()
    today = datetime(2024, 7, 15).date()
    gm = _membership(club, "gm@test.com", is_game_master=True)
    session = _session(
        club,
        starts_at=_ny(today, 19),
        ends_at=_ny(today, 22),
        title="Evening session",
        gm=gm,
    )  # 19:00-22:00 EDT

    result = upcoming_sessions(club, _ny(today, 23), None, 10)  # 23:00 EDT
    assert [s["id"] for s in result["sessions"]] == [session.pk]

    result = upcoming_sessions(club, _ny(today + timedelta(days=1), 1), None, 10)  # 01:00 EDT
    assert result["sessions"] == []


def test_session_ending_after_midnight_counts_through_end_day():
    club = _club()
    today = datetime(2024, 7, 15).date()
    gm = _membership(club, "gm@test.com", is_game_master=True)
    session = _session(
        club,
        starts_at=_ny(today, 23),  # 23:00 EDT today = 03:00 UTC tomorrow
        ends_at=_ny(today + timedelta(days=1), 2),  # 02:00 EDT tomorrow = 06:00 UTC
        title="Past midnight",
        gm=gm,
    )

    # 01:00 EDT the next day: session already started locally but ends today.
    result = upcoming_sessions(club, _ny(today + timedelta(days=1), 1), None, 10)
    assert [s["id"] for s in result["sessions"]] == [session.pk]


def test_cancelled_sessions_included_marked_no_answer():
    club = _club()
    now = _ny(datetime(2024, 7, 15).date(), 10)
    membership = _membership(club, "player@test.com")
    gm = _membership(club, "gm@test.com", is_game_master=True)
    cancelled = _session(
        club,
        starts_at=_ny(datetime(2024, 7, 17).date(), 10),
        cancelled=True,
        title="Cancelled",
        gm=gm,
    )
    PlayerRSVP.objects.create(session=cancelled, member=membership, answer="yes")

    result = upcoming_sessions(club, now, membership, 10)
    rows = {s["id"]: s for s in result["sessions"]}
    assert cancelled.pk in rows
    assert rows[cancelled.pk]["cancelled"] is True
    assert rows[cancelled.pk]["my_answer"] is None  # cancelled rows get no answer badge


def test_ordering_by_starts_at_then_id_and_limit():
    club = _club()
    now = _ny(datetime(2024, 7, 15).date(), 10)
    gm = _membership(club, "gm@test.com", is_game_master=True)
    today = datetime(2024, 7, 15).date()
    late = _session(club, starts_at=_ny(today, 20), title="Late", gm=gm)
    early = _session(club, starts_at=_ny(today, 12), title="Early", gm=gm)
    same_start_later_id = _session(club, starts_at=_ny(today, 12), title="Same start", gm=gm)

    result = upcoming_sessions(club, now, None, 10)
    ids = [s["id"] for s in result["sessions"]]
    assert ids == [early.pk, same_start_later_id.pk, late.pk]

    result = upcoming_sessions(club, now, None, 2)
    assert [s["id"] for s in result["sessions"]] == [early.pk, same_start_later_id.pk]


def test_yes_count_annotated_and_one_query_for_all_answers():
    club = _club()
    now = _ny(datetime(2024, 7, 15).date(), 10)
    membership = _membership(club, "player@test.com")
    gm = _membership(club, "gm@test.com", is_game_master=True)
    today = datetime(2024, 7, 15).date()
    s1 = _session(club, starts_at=_ny(today, 12), title="S1", gm=gm)
    s2 = _session(club, starts_at=_ny(today, 14), title="S2", gm=gm)
    s3 = _session(club, starts_at=_ny(today, 16), title="S3", gm=gm)
    PlayerRSVP.objects.create(session=s1, member=membership, answer="yes")
    PlayerRSVP.objects.create(session=s1, member=_membership(club, "a@test.com"), answer="yes")
    PlayerRSVP.objects.create(session=s2, member=membership, answer="maybe")

    with CaptureQueriesContext(connection) as ctx:
        result = upcoming_sessions(club, now, membership, 10)
    assert len(ctx.captured_queries) == 2  # sessions + one bulk member-answer query

    rows = {s["id"]: s for s in result["sessions"]}
    assert rows[s1.pk]["yes_count"] == 2
    assert rows[s2.pk]["yes_count"] == 0
    assert rows[s3.pk]["yes_count"] == 0


def test_my_answer_values_yes_maybe_no_none_none_for_cancelled():
    club = _club()
    now = _ny(datetime(2024, 7, 15).date(), 10)
    membership = _membership(club, "player@test.com")
    gm = _membership(club, "gm@test.com", is_game_master=True)
    today = datetime(2024, 7, 15).date()
    s_yes = _session(club, starts_at=_ny(today, 12), title="Yes", gm=gm)
    s_maybe = _session(club, starts_at=_ny(today, 13), title="Maybe", gm=gm)
    s_no = _session(club, starts_at=_ny(today, 14), title="No", gm=gm)
    s_none = _session(club, starts_at=_ny(today, 15), title="None", gm=gm)
    s_cancelled = _session(club, starts_at=_ny(today, 16), title="Cancelled", cancelled=True, gm=gm)
    PlayerRSVP.objects.create(session=s_yes, member=membership, answer="yes")
    PlayerRSVP.objects.create(session=s_maybe, member=membership, answer="maybe")
    PlayerRSVP.objects.create(session=s_no, member=membership, answer="no")
    PlayerRSVP.objects.create(session=s_cancelled, member=membership, answer="yes")

    result = upcoming_sessions(club, now, membership, 10)
    answers = {s["id"]: s["my_answer"] for s in result["sessions"]}
    assert answers[s_yes.pk] == "yes"
    assert answers[s_maybe.pk] == "maybe"
    assert answers[s_no.pk] == "no"
    assert answers[s_none.pk] == "none"
    assert answers[s_cancelled.pk] is None

    # No membership: every non-cancelled row reports "none".
    result = upcoming_sessions(club, now, None, 10)
    assert all(s["my_answer"] == "none" for s in result["sessions"] if not s["cancelled"])


def test_is_next_and_when_text():
    club = _club()
    today = datetime(2024, 7, 15).date()
    now = _ny(today, 10)
    gm = _membership(club, "gm@test.com", is_game_master=True)
    cancelled_first = _session(
        club,
        starts_at=_ny(today, 12),
        title="Cancelled first",
        cancelled=True,
        gm=gm,
    )
    _session(
        club,
        starts_at=_ny(today + timedelta(days=1), 10),
        title="Tomorrow",
        gm=gm,
    )
    _session(
        club,
        starts_at=_ny(today + timedelta(days=3), 10),
        title="Days",
        gm=gm,
    )
    _session(
        club,
        starts_at=_ny(today + timedelta(days=14), 10),
        title="Weeks",
        gm=gm,
    )
    _session(
        club,
        starts_at=_ny(today + timedelta(days=15), 10),
        title="Weeks 2",
        gm=gm,
    )

    # First non-cancelled row carries is_next and when_text; later rows do not.
    result = upcoming_sessions(club, now, None, 10)
    rows = result["sessions"]
    assert rows[0]["id"] == cancelled_first.pk and rows[0]["is_next"] is False
    assert rows[0]["when_text"] is None
    assert rows[1]["is_next"] is True
    assert rows[1]["when_text"] == "tomorrow"
    assert rows[2]["is_next"] is False
    assert rows[2]["when_text"] is None
    assert rows[3]["is_next"] is False
    assert rows[3]["when_text"] is None
    assert rows[4]["is_next"] is False
    assert rows[4]["when_text"] is None

    # When the first non-cancelled session is today.
    today_club = _club(slug="today-club")
    gm_t = _membership(today_club, "gt@test.com", is_game_master=True)
    _session(
        today_club,
        starts_at=_ny(today, 16),
        title="Today",
        gm=gm_t,
    )
    result = upcoming_sessions(today_club, now, None, 10)
    assert result["sessions"][0]["is_next"] is True
    assert result["sessions"][0]["when_text"] == "today"

    # In N days / in N weeks (14+ days) when that row is first.
    days_club = _club(slug="days-club")
    gm_d = _membership(days_club, "gd@test.com", is_game_master=True)
    _session(
        days_club,
        starts_at=_ny(today + timedelta(days=3), 10),
        title="Days",
        gm=gm_d,
    )
    result = upcoming_sessions(days_club, now, None, 10)
    assert result["sessions"][0]["when_text"] == "in 3 days"

    weeks_club = _club(slug="weeks-club")
    gm_w = _membership(weeks_club, "gw@test.com", is_game_master=True)
    _session(
        weeks_club,
        starts_at=_ny(today + timedelta(days=14), 10),
        title="Weeks",
        gm=gm_w,
    )
    result = upcoming_sessions(weeks_club, now, None, 10)
    assert result["sessions"][0]["when_text"] == "in 2 weeks"
    weeks2_club = _club(slug="weeks2-club")
    gm_w2 = _membership(weeks2_club, "gw2@test.com", is_game_master=True)
    _session(
        weeks2_club,
        starts_at=_ny(today + timedelta(days=15), 10),
        title="Weeks 2",
        gm=gm_w2,
    )
    result = upcoming_sessions(weeks2_club, now, None, 10)
    assert result["sessions"][0]["when_text"] == "in 2 weeks"

    # All cancelled: nothing is next.
    cancelled_club = _club(slug="cancelled-club")
    _membership(cancelled_club, "gc@test.com", is_game_master=True)
    _session(
        cancelled_club,
        starts_at=_ny(today, 12),
        title="C1",
        cancelled=True,
    )
    result = upcoming_sessions(cancelled_club, now, None, 10)
    assert all(not s["is_next"] for s in result["sessions"])
    assert all(s["when_text"] is None for s in result["sessions"])


def test_first_month_returned_or_none():
    club = _club()
    now = _ny(datetime(2024, 7, 15).date(), 10)
    gm = _membership(club, "gm@test.com", is_game_master=True)
    _session(
        club,
        starts_at=_ny(datetime(2024, 7, 15).date(), 10),
        title="July",
        gm=gm,
    )
    _session(
        club,
        starts_at=_ny(datetime(2024, 8, 5).date(), 10),
        title="August",
        gm=gm,
    )

    result = upcoming_sessions(club, now, None, 10)
    assert result["first_month"] == (2024, 7)

    empty_club = _club(slug="empty-club")
    result = upcoming_sessions(empty_club, now, None, 10)
    assert result["sessions"] == []
    assert result["first_month"] is None


def test_club_scoped_other_clubs_excluded():
    club = _club()
    other = _club(slug="other", name="Other")
    now = _ny(datetime(2024, 7, 15).date(), 10)
    gm = _membership(club, "gm@test.com", is_game_master=True)
    _session(
        club,
        starts_at=_ny(datetime(2024, 7, 15).date(), 10),
        title="Ours",
        gm=gm,
    )
    _session(
        other,
        starts_at=_ny(datetime(2024, 7, 15).date(), 10),
        title="Theirs",
        gm=_membership(other, "g2@test.com", is_game_master=True),
    )

    result = upcoming_sessions(club, now, None, 10)
    assert len(result["sessions"]) == 1
    assert result["sessions"][0]["title"] == "Ours"


def test_zone_label_uses_club_zone_key():
    club = _club()
    now = _ny(datetime(2024, 7, 15).date(), 10)
    gm = _membership(club, "gm@test.com", is_game_master=True)
    _session(club, starts_at=_ny(datetime(2024, 7, 15).date(), 10), title="S", gm=gm)

    result = upcoming_sessions(club, now, None, 10)
    assert result["sessions"][0]["zone_label"] == "America/New_York"


def test_partial_renders_rows_and_empty_state():
    club = _club()
    gm = _membership(club, "gm@test.com", is_game_master=True)
    membership = _membership(club, "player@test.com")
    today = datetime(2024, 7, 15).date()
    session = _session(club, starts_at=_ny(today, 16), title="Next session", gm=gm)
    _session(
        club,
        starts_at=_ny(today + timedelta(days=1), 10),
        title="Cancelled session",
        cancelled=True,
        gm=gm,
    )
    PlayerRSVP.objects.create(session=session, member=membership, answer="yes")

    result = upcoming_sessions(club, _ny(today, 10), membership, 10)
    html = render_to_string(
        "play_sessions/_coming_up.html",
        {
            "coming_up": result["sessions"],
            "first_month": result["first_month"],
            "club": club,
            "membership": membership,
            "can_manage_sessions": True,
        },
    )
    assert "Next session" in html
    assert "Next" in html
    assert "today" in html
    assert "Cancelled session" in html
    assert "Cancelled" in html
    assert "You: Yes" in html
    assert "GM:" in html

    # Empty state.
    html = render_to_string(
        "play_sessions/_coming_up.html",
        {
            "coming_up": [],
            "first_month": None,
            "club": club,
            "membership": membership,
            "can_manage_sessions": True,
        },
    )
    assert "No sessions are scheduled yet." in html
    assert "Add a session" in html
    assert club.slug in html

    html = render_to_string(
        "play_sessions/_coming_up.html",
        {
            "coming_up": [],
            "first_month": None,
            "club": club,
            "membership": None,
            "can_manage_sessions": False,
        },
    )
    assert "Add a session" not in html


def test_can_rsvp_true_for_false_for_cancelled_and_started():
    """can_rsvp is true for a future session, false when cancelled or started."""
    club = _club(timezone_name="UTC")
    now = datetime(2024, 7, 15, 10, tzinfo=UTC)
    membership = _membership(club, "player@test.com")
    gm = _membership(club, "gm@test.com", is_game_master=True)

    future = _session(club, starts_at=now + timedelta(days=1), title="Future", gm=gm)
    cancelled = _session(
        club, starts_at=now + timedelta(days=2), title="Cancelled", cancelled=True, gm=gm
    )
    started = _session(club, starts_at=now - timedelta(hours=1), title="Started", gm=gm)

    result = upcoming_sessions(club, now, membership, 10)
    rows = {s["id"]: s for s in result["sessions"]}
    assert rows[future.pk]["can_rsvp"] is True
    assert rows[cancelled.pk]["can_rsvp"] is False
    assert rows[started.pk]["can_rsvp"] is False


def test_partial_shows_rsvp_form_only_when_show_rsvp():
    """The partial renders the RSVP form only when show_rsvp is set."""
    club = _club(timezone_name="UTC")
    gm = _membership(club, "gm@test.com", is_game_master=True)
    membership = _membership(club, "player@test.com")
    _session(club, starts_at=datetime(2024, 7, 15, 16, tzinfo=UTC), title="Next session", gm=gm)

    result = upcoming_sessions(club, datetime(2024, 7, 15, 10, tzinfo=UTC), membership, 10)

    common = {
        "coming_up": result["sessions"],
        "first_month": result["first_month"],
        "club": club,
        "membership": membership,
        "can_manage_sessions": True,
    }

    html = render_to_string(
        "play_sessions/_coming_up.html",
        {**common, "show_rsvp": True, "rsvp_next": "/c/club/dashboard/"},
    )
    assert html.count('name="answer"') == 3
    assert 'value="yes"' in html
    assert 'value="maybe"' in html
    assert 'value="no"' in html
    assert "Not answered" in html

    # Without show_rsvp (club home and sessions page contexts) no form is rendered.
    html = render_to_string("play_sessions/_coming_up.html", common)
    assert 'name="answer"' not in html
    assert "Not answered" in html


def test_club_home_and_calendar_have_no_rsvp_form(client, club, game_master):
    """Club home and the sessions page keep badge and link only, no RSVP form."""
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    session = _session(
        club, starts_at=timezone.now() + timedelta(days=2), title="Soon", gm=gm_membership
    )
    rsvp_action = reverse(
        "play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk}
    )

    client.force_login(game_master)
    for url in (
        reverse("club_home", kwargs={"club_slug": club.slug}),
        reverse("play_sessions:calendar", kwargs={"club_slug": club.slug}),
    ):
        response = client.get(url)
        assert response.status_code == 200, url
        assert rsvp_action not in response.content.decode(), url


def test_dashboard_card_heading_shows_once(client, club, player, character):
    """The dashboard card shows the 'Upcoming sessions' heading exactly once."""
    club.timezone = "UTC"
    club.save()
    gm = Membership.objects.filter(club=club, is_game_master=True).first()
    if gm is None:
        gm_user = User.objects.create_user(email="gm@test.com", password="pw", display_name="Gm")
        gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    _session(club, starts_at=timezone.now() + timedelta(days=2), title="Soon", gm=gm)

    client.force_login(player)
    response = client.get(reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug}))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Soon" in content
    assert content.count("Upcoming sessions") == 1
