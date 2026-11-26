"""Tests for the session calendar, next-session block and calendar feed (P3)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions.calendar import month_grid, next_session, parse_month
from play_sessions.feed import build_ics, get_or_create_token
from play_sessions.models import PlayerRSVP, PlaySession
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("P3")]


def _session(
    club,
    title,
    starts_at,
    ends_at=None,
    cancelled=False,
    gm=None,
    location="",
    notes="",
    recap="",
    gm_notes="",
):
    return PlaySession.objects.create(
        club=club,
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        cancelled=cancelled,
        game_master=gm,
        location=location,
        notes=notes,
        recap=recap,
        gm_notes=gm_notes,
    )


def test_parse_month_bad_input_falls_back_to_today():
    today = datetime(2025, 6, 10).date()
    assert parse_month(None, today) == (2025, 6)
    assert parse_month("not-a-month", today) == (2025, 6)
    assert parse_month("9999-13", today) == (2025, 6)
    assert parse_month("2025-07", today) == (2025, 7)


def test_month_grid_groups_by_club_zone_day(club, game_master):
    """23:30 and 00:30 club time land on different club-local days."""
    club.timezone = "America/New_York"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)

    # 23:30 NY on June 15 = June 16 03:30 UTC -> club-local date June 15
    _session(
        club,
        "Late night",
        timezone.datetime(2025, 6, 16, 3, 30, tzinfo=UTC),
        gm=gm_membership,
    )
    # 00:30 NY on June 16 = June 16 04:30 UTC -> club-local date June 16
    _session(
        club,
        "After midnight",
        timezone.datetime(2025, 6, 16, 4, 30, tzinfo=UTC),
        gm=gm_membership,
    )

    grid = month_grid(club, 2025, 6, datetime(2025, 6, 10).date())
    by_date = {day["date"]: day["sessions"] for week in grid["weeks"] for day in week}
    june_15 = [s.title for s in by_date.get(datetime(2025, 6, 15).date(), [])]
    june_16 = [s.title for s in by_date.get(datetime(2025, 6, 16).date(), [])]
    assert "Late night" in june_15
    assert "After midnight" in june_16


def test_month_grid_excludes_other_club(club, game_master):
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    club.timezone = "UTC"
    club.save()
    other_club.timezone = "UTC"
    other_club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "Club A", timezone.datetime(2025, 6, 15, 20, 0, tzinfo=UTC), gm=gm_membership)
    _session(other_club, "Club B", timezone.datetime(2025, 6, 15, 20, 0, tzinfo=UTC))

    grid = month_grid(club, 2025, 6, datetime(2025, 6, 10).date())
    titles = [s.title for week in grid["weeks"] for day in week for s in day["sessions"]]
    assert "Club A" in titles
    assert "Club B" not in titles


def test_month_grid_dst_week(club, game_master):
    """Sessions group by club-local date across a DST transition (Nov 2024, US)."""
    club.timezone = "America/New_York"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)

    # Nov 3 2024 01:30 NY (DST fall-back, fold=0) = Nov 3 05:30 UTC
    _session(club, "Fall back", timezone.datetime(2024, 11, 3, 5, 30, tzinfo=UTC), gm=gm_membership)
    # Nov 10 2024 14:00 NY (EST, UTC-5) = Nov 10 19:00 UTC
    _session(club, "Std time", timezone.datetime(2024, 11, 10, 19, 0, tzinfo=UTC), gm=gm_membership)

    grid = month_grid(club, 2024, 11, datetime(2024, 11, 10).date())
    by_date = {day["date"]: day["sessions"] for week in grid["weeks"] for day in week}
    nov_3 = [s.title for s in by_date.get(datetime(2024, 11, 3).date(), [])]
    nov_10 = [s.title for s in by_date.get(datetime(2024, 11, 10).date(), [])]
    assert "Fall back" in nov_3
    assert "Std time" in nov_10


def test_next_session_skips_cancelled_and_past(club, game_master):
    club.timezone = "America/New_York"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    now = timezone.now()

    _session(club, "Cancelled", now + timedelta(days=1), cancelled=True, gm=gm_membership)
    _session(club, "Past", now - timedelta(days=2), gm=gm_membership)
    _session(club, "Upcoming", now + timedelta(days=3), gm=gm_membership)

    result = next_session(club, now)
    assert result is not None
    assert result["title"] == "Upcoming"
    assert result["yes_count"] == 0

    PlaySession.objects.filter(club=club).delete()
    assert next_session(club, now) is None


def test_next_session_is_club_scoped(club, game_master):
    now = timezone.now()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    other_club.timezone = "UTC"
    other_club.save()
    _session(club, "Club A", now + timedelta(days=1), gm=gm_membership)
    _session(other_club, "Club B", now + timedelta(days=1), gm=gm_membership)
    assert next_session(club, now)["title"] == "Club A"


def test_yes_count_counts_only_yes(club, game_master, player, other_player):
    club.timezone = "America/New_York"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    owner = Membership.objects.get(user=player, club=club)
    other_owner = Membership.objects.get(user=other_player, club=club)
    Character.objects.create(club=club, owner=owner, name="C1")
    Character.objects.create(club=club, owner=other_owner, name="C2")

    session = _session(club, "RSVP session", timezone.now() + timedelta(days=1), gm=gm_membership)
    PlayerRSVP.objects.create(
        session=session, member=owner, answer=PlayerRSVP.Answer.YES, answered_by=player
    )
    PlayerRSVP.objects.create(
        session=session,
        member=other_owner,
        answer=PlayerRSVP.Answer.MAYBE,
        answered_by=other_player,
    )

    grid = month_grid(
        club, timezone.localdate().year, timezone.localdate().month, timezone.localdate()
    )
    for week in grid["weeks"]:
        for day in week:
            for s in day["sessions"]:
                if s.pk == session.pk:
                    assert s.yes_count == 1
                    return
    pytest.fail("Session not found in grid")


def test_ics_content(club, game_master):
    club.timezone = "America/New_York"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    session = _session(
        club,
        "Title, with ; semi \\ backslash\nand newline",
        timezone.datetime(2024, 6, 15, 22, 0, tzinfo=UTC),
        ends_at=timezone.datetime(2024, 6, 16, 1, 0, tzinfo=UTC),
        gm=gm_membership,
        location="The Tavern",
        notes="Bring dice,\nand snacks",
        recap="secret recap",
        gm_notes="secret gm notes",
    )
    ics = build_ics(club, timezone.datetime(2024, 6, 20, 12, 0, tzinfo=UTC))

    # CRLF line ends
    assert "\r\n" in ics
    assert ics.endswith("\r\n")

    # UTC DTSTART / DTEND
    assert "DTSTART:20240615T220000Z" in ics
    assert "DTEND:20240616T010000Z" in ics

    # Escaping of , ; \ and newline in title/notes
    assert "Title\, with \; semi \\\\ backslash\\nand newline" in ics
    assert "Bring dice\\,\\nand snacks" in ics

    # recap / gm_notes never in the feed
    assert "secret recap" not in ics
    assert "secret gm notes" not in ics

    # STATUS
    assert "STATUS:CONFIRMED" in ics

    # Game master in description
    assert f"Game master: {game_master.display_name}" in ics

    # Calendar properties
    assert "BEGIN:VCALENDAR" in ics
    assert "VERSION:2.0" in ics
    assert "CALSCALE:GREGORIAN" in ics
    assert f"X-WR-CALNAME:{club.name}" in ics
    assert f"UID:play-session-{session.pk}@{club.slug}" in ics


def test_ics_cancelled_status(club, game_master):
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(
        club,
        "Cancelled session",
        timezone.datetime(2024, 6, 15, 22, 0, tzinfo=UTC),
        cancelled=True,
        gm=gm_membership,
    )
    ics = build_ics(club, timezone.datetime(2024, 6, 20, 12, 0, tzinfo=UTC))
    assert "STATUS:CANCELLED" in ics


def test_ics_line_folding(club, game_master):
    """Every physical line folds at 75 octets."""
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "A" * 200, timezone.datetime(2024, 6, 15, 22, 0, tzinfo=UTC), gm=gm_membership)
    ics = build_ics(club, timezone.datetime(2024, 6, 20, 12, 0, tzinfo=UTC))
    for raw in ics.split("\r\n"):
        if raw:
            assert len(raw.encode("utf-8")) <= 75, raw


def test_public_feed_logged_out(client, club, game_master):
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "Public session", timezone.now() + timedelta(days=1), gm=gm_membership)
    token = get_or_create_token(club)
    response = Client().get(reverse("play_sessions_public:feed", args=[token]))
    assert response.status_code == 200
    assert response["Content-Type"] == "text/calendar; charset=utf-8"
    assert "private" in response["Cache-Control"]
    assert b"Public session" in response.content


def test_public_feed_wrong_token_404(client):
    assert client.get(reverse("play_sessions_public:feed", args=["wrong-token"])).status_code == 404


def test_public_feed_empty_token_404(client):
    # An empty token cannot match the slug converter, so it routes to 404.
    assert client.get("/sessions/feed/.ics").status_code == 404


def test_feed_token_created_once_and_stable(club, game_master):
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "S", timezone.now() + timedelta(days=1), gm=gm_membership)
    t1 = get_or_create_token(club)
    t2 = get_or_create_token(club)
    assert t1 == t2
    assert len(t1) == 43  # token_urlsafe(32)


def test_feed_token_unique_per_club(club):
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    t1 = get_or_create_token(club)
    t2 = get_or_create_token(other_club)
    assert t1 != t2


def test_feed_reset_admin_invalidates(client, club, game_master, club_admin):
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "S", timezone.now() + timedelta(days=1), gm=gm_membership)
    token = get_or_create_token(club)
    feed_url = reverse("play_sessions_public:feed", args=[token])
    assert client.get(feed_url).status_code == 200

    client.force_login(club_admin)
    reset_url = reverse("play_sessions:feed_reset", kwargs={"club_slug": club.slug})
    # GET is refused
    assert client.get(reset_url).status_code == 405
    # POST resets
    r = client.post(reset_url)
    assert r.status_code in (301, 302)
    # Old token now 404
    assert client.get(feed_url).status_code == 404
    # New token works
    new_token = get_or_create_token(club)
    assert new_token != token
    assert client.get(reverse("play_sessions_public:feed", args=[new_token])).status_code == 200


def test_feed_reset_non_admin_forbidden(client, club, game_master, player):
    reset_url = reverse("play_sessions:feed_reset", kwargs={"club_slug": club.slug})
    client.force_login(player)
    assert client.post(reset_url).status_code == 403
    client.force_login(game_master)
    assert client.post(reset_url).status_code == 403


def test_calendar_page_shows_grid_and_list(client, club, game_master):
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "Grid session", timezone.now() + timedelta(days=1), gm=gm_membership)
    client.force_login(game_master)
    url = reverse("play_sessions:calendar", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Grid session" in content
    # Both grid and list are present (hidden by CSS class only)
    assert "d-none d-md-block" in content
    assert "d-md-none" in content
    # Feed link present
    assert "Add to calendar" in content
    assert "webcal://" in content


def test_calendar_prev_next_month_links(client, club, game_master):
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "S", timezone.now() + timedelta(days=1), gm=gm_membership)
    client.force_login(game_master)
    url = reverse("play_sessions:calendar", kwargs={"club_slug": club.slug})
    response = client.get(url)
    content = response.content.decode()
    assert "?month=" in content
    # Bad month falls back to current month (page still 200)
    assert client.get(url + "?month=not-a-month").status_code == 200


def test_nav_sessions_present_for_member(client, club, player, game_master):
    client.force_login(player)
    gm_membership = Membership.objects.get(user=game_master, club=club)
    session = _session(club, "S", timezone.now() + timedelta(days=1), gm=gm_membership)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert "Sessions" in response.content.decode()


def test_club_home_next_session_block_gm_and_admin(client, club, game_master, club_admin):
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "Coming up", timezone.now() + timedelta(days=2), gm=gm_membership)
    for user in (game_master, club_admin):
        client.force_login(user)
        response = client.get(reverse("club_home", kwargs={"club_slug": club.slug}))
        assert response.status_code == 200, f"{user.email} club_home"
        assert "Coming up" in response.content.decode()
        client.logout()


def test_club_home_player_redirect_unchanged(client, club, player):
    client.force_login(player)
    response = client.get(reverse("club_home", kwargs={"club_slug": club.slug}))
    assert response.status_code == 302
    assert response.url == reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug})


def test_player_dashboard_next_session_card(client, club, player, character):
    club.timezone = "UTC"
    club.save()
    gm = Membership.objects.filter(club=club, is_game_master=True).first()
    if gm is None:
        gm_user = User.objects.create_user(email="gm2@test.com", password="pw", display_name="Gm2")
        gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    _session(club, "Dashboard session", timezone.now() + timedelta(days=2), gm=gm)
    client.force_login(player)
    response = client.get(reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug}))
    assert response.status_code == 200
    assert "Dashboard session" in response.content.decode()


def _gm_membership(club):
    gm = Membership.objects.filter(club=club, is_game_master=True).first()
    if gm is None:
        gm_user = User.objects.create_user(email="gm@test.com", password="pw", display_name="Gm")
        gm = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    return gm


def test_player_dashboard_shows_upcoming_list_up_to_three(client, club, player, character):
    club.timezone = "UTC"
    club.save()
    gm = _gm_membership(club)
    today = timezone.now()
    _session(club, "Session One", today + timedelta(days=1), gm=gm)
    _session(club, "Session Two", today + timedelta(days=2), gm=gm)
    _session(club, "Session Three", today + timedelta(days=3), gm=gm)
    client.force_login(player)
    response = client.get(reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug}))
    assert response.status_code == 200
    content = response.content.decode()
    for title in ("Session One", "Session Two", "Session Three"):
        assert title in content
    assert reverse("play_sessions:calendar", kwargs={"club_slug": club.slug}) in content


def test_player_dashboard_shows_fewer_than_three_and_empty(client, club, player, character):
    club.timezone = "UTC"
    club.save()
    gm = _gm_membership(club)
    _session(club, "Lone session", timezone.now() + timedelta(days=1), gm=gm)
    client.force_login(player)
    response = client.get(reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug}))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Lone session" in content
    assert "No sessions are scheduled yet." not in content

    PlaySession.objects.filter(club=club).delete()
    response = client.get(reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug}))
    content = response.content.decode()
    assert "No sessions are scheduled yet." in content


def test_player_dashboard_cancelled_marked_no_answer_badge(client, club, player, character):
    club.timezone = "UTC"
    club.save()
    gm = _gm_membership(club)
    player_membership = Membership.objects.get(user=player, club=club)
    cancelled = _session(
        club,
        "Cancelled session",
        timezone.now() + timedelta(days=1),
        cancelled=True,
        gm=gm,
    )
    PlayerRSVP.objects.create(session=cancelled, member=player_membership, answer="yes")
    client.force_login(player)
    response = client.get(reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug}))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Cancelled session" in content
    assert "Cancelled" in content
    assert "You: Yes" not in content


def test_dashboard_list_matches_upcoming_sessions_query(client, club, player, character):
    """Dashboard list uses the shared query: same order, is_next and when_text."""
    club.timezone = "UTC"
    club.save()
    gm = _gm_membership(club)
    membership = Membership.objects.get(user=player, club=club)
    today = timezone.now()
    s_one = _session(club, "Session One", today + timedelta(days=1), gm=gm)
    s_two = _session(club, "Session Two", today + timedelta(days=3), gm=gm)
    _session(club, "Session Three", today + timedelta(days=5), gm=gm)

    from play_sessions.upcoming import upcoming_sessions

    data = upcoming_sessions(club, today, membership, 3)
    rows = data["sessions"]
    assert [r["id"] for r in rows] == [s_one.pk, s_two.pk, rows[2]["id"]]
    assert rows[0]["is_next"] is True
    assert rows[0]["when_text"] == "tomorrow"
    assert rows[1]["is_next"] is False
    assert rows[1]["when_text"] is None

    client.force_login(player)
    response = client.get(reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug}))
    assert response.status_code == 200
    content = response.content.decode()
    # Same order as the shared query, first non-cancelled row is "Next".
    assert content.index("Session One") < content.index("Session Two")
    assert "Next" in content
    assert "tomorrow" in content


def test_club_home_shows_upcoming_list_gm_and_admin(client, club, game_master, club_admin):
    club.timezone = "UTC"
    club.save()
    gm = _gm_membership(club)
    _session(club, "Club home session", timezone.now() + timedelta(days=2), gm=gm)
    calendar_url = reverse("play_sessions:calendar", kwargs={"club_slug": club.slug})
    for user in (game_master, club_admin):
        client.force_login(user)
        response = client.get(reverse("club_home", kwargs={"club_slug": club.slug}))
        assert response.status_code == 200, f"{user.email} club_home"
        content = response.content.decode()
        assert "Club home session" in content
        assert calendar_url in content
        client.logout()


def test_isolation_club_b_not_in_club_a(client, club, game_master):
    club.timezone = "UTC"
    club.save()
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    other_club.timezone = "UTC"
    other_club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(club, "Club A session", timezone.now() + timedelta(days=1), gm=gm_membership)
    _session(other_club, "Club B session", timezone.now() + timedelta(days=1), gm=gm_membership)

    client.force_login(game_master)
    # Club A page
    a = client.get(reverse("play_sessions:calendar", kwargs={"club_slug": club.slug}))
    assert "Club A session" in a.content.decode()
    assert "Club B session" not in a.content.decode()
    # Club A feed only has Club A events
    token = get_or_create_token(club)
    feed = client.get(reverse("play_sessions_public:feed", args=[token]))
    assert b"Club A session" in feed.content
    assert b"Club B session" not in feed.content
    # Another club's ?month= leaks nothing
    b = client.get(
        reverse("play_sessions:calendar", kwargs={"club_slug": club.slug}) + "?month=2025-01"
    )
    assert b.status_code == 200


def test_ics_crlf_notes_do_not_leak_bare_cr(club, game_master):
    """Browser textareas submit CRLF; the .ics must not carry a stray CR."""
    club.timezone = "UTC"
    club.save()
    gm_membership = Membership.objects.get(user=game_master, club=club)
    _session(
        club,
        "Crlf",
        datetime(2024, 6, 15, 22, 0, tzinfo=UTC),
        gm=gm_membership,
        notes="line1\r\nline2\rline3",
    )
    ics = build_ics(club, datetime(2024, 6, 20, 12, 0, tzinfo=UTC))
    assert "line1\\nline2\\nline3" in ics.replace("\r\n ", "")
    # Every CR is part of a CRLF pair.
    assert ics.count("\r") == ics.count("\r\n")
    assert "\r" not in ics.replace("\r\n", "")


def test_feed_reset_before_any_calendar_view(client, club, club_admin):
    """Reset must not 500 when no SessionSettings row exists yet."""
    from play_sessions.models import SessionSettings

    assert not SessionSettings.objects.filter(club=club).exists()
    client.force_login(club_admin)
    reset_url = reverse("play_sessions:feed_reset", kwargs={"club_slug": club.slug})
    assert client.post(reset_url).status_code in (301, 302)
    token = SessionSettings.objects.get(club=club).feed_token
    assert token
    assert client.get(reverse("play_sessions_public:feed", args=[token])).status_code == 200


def test_calendar_month_nav_outside_grid_and_full_width(client, club, player):
    """Month nav shows at every width (not inside the d-none grid); list is not a side column."""
    client.force_login(player)
    r = client.get(reverse("play_sessions:calendar", kwargs={"club_slug": club.slug}))
    html = r.content.decode()
    nav_pos = html.index("sessions-nav")
    grid_pos = html.index("sessions-grid")
    assert nav_pos < grid_pos
    assert "d-none d-md-block" in html
    assert "col-md-4" not in html
