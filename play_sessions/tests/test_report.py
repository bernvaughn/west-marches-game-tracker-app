"""Tests for P7 (sheet history) and P8 (attendance report)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions.models import PlaySession, SessionAttendance
from play_sessions.report import parse_range, report_rows, sheet_history
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def _make_user(email):
    return User.objects.create_user(email=email, password="pass12345678")


def _make_club(timezone_name="America/New_York"):
    return Club.objects.create(name="Report Club", slug="report-club", timezone=timezone_name)


def _make_membership(user, club, is_admin=False, is_gm=False):
    return Membership.objects.create(
        user=user, club=club, is_club_admin=is_admin, is_game_master=is_gm
    )


def _make_character(name, club, owner):
    return Character.objects.create(name=name, club=club, owner=owner)


def _make_session(club, title, starts_at, game_master, cancelled=False, **kwargs):
    return PlaySession.objects.create(
        club=club,
        title=title,
        starts_at=starts_at,
        game_master=game_master,
        cancelled=cancelled,
        **kwargs,
    )


def _make_attendance(session, character, played=True):
    return SessionAttendance.objects.create(session=session, character=character, played=played)


# ---------------------------------------------------------------------------
# parse_range
# ---------------------------------------------------------------------------


def test_parse_range_blank():
    start, end, error = parse_range({}, None)
    assert start is None
    assert end is None
    assert error is None


def test_parse_range_start_and_end():
    start, end, error = parse_range({"start": "2024-01-01", "end": "2024-01-31"}, None)
    assert start.isoformat() == "2024-01-01"
    assert end.isoformat() == "2024-01-31"
    assert error is None


def test_parse_range_bad_date():
    start, end, error = parse_range({"start": "not-a-date"}, None)
    assert start is None
    assert end is None
    assert error is not None


def test_parse_range_end_before_start():
    start, end, error = parse_range({"start": "2024-02-01", "end": "2024-01-01"}, None)
    assert start is None
    assert end is None
    assert error is not None


# ---------------------------------------------------------------------------
# P8: report rows (character / player grouping)
# ---------------------------------------------------------------------------


def test_two_characters_one_player_count_once_for_player():
    club = _make_club()
    player_user = _make_user("player@test.com")
    player_mem = _make_membership(player_user, club)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)

    char_a = _make_character("Char A", club, player_mem)
    char_b = _make_character("Char B", club, player_mem)

    session = _make_session(club, "Session 1", timezone.now(), gm_mem)
    _make_attendance(session, char_a, played=True)
    _make_attendance(session, char_b, played=True)

    characters, players = report_rows(club, None, None)

    assert len(characters) == 2
    assert {c["name"] for c in characters} == {"Char A", "Char B"}
    assert all(c["sessions"] == 1 for c in characters)
    assert len(players) == 1
    assert players[0]["sessions"] == 1  # player counts once for the session
    assert players[0]["name"] == player_user.display_name or player_user.email


def test_played_false_and_cancelled_never_count():
    club = _make_club()
    player_user = _make_user("player@test.com")
    player_mem = _make_membership(player_user, club)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)

    char = _make_character("Char", club, player_mem)

    played_session = _make_session(club, "Played", timezone.now(), gm_mem)
    _make_attendance(played_session, char, played=True)

    absent_session = _make_session(club, "Absent", timezone.now() + timedelta(days=1), gm_mem)
    _make_attendance(absent_session, char, played=False)

    cancelled_session = _make_session(
        club, "Cancelled", timezone.now() + timedelta(days=2), gm_mem, cancelled=True
    )
    _make_attendance(cancelled_session, char, played=True)

    characters, players = report_rows(club, None, None)

    assert len(characters) == 1
    assert characters[0]["sessions"] == 1
    assert characters[0]["name"] == "Char"
    assert len(players) == 1
    assert players[0]["sessions"] == 1


# ---------------------------------------------------------------------------
# P8: date range filter (club-local, inclusive, DST safe)
# ---------------------------------------------------------------------------


def test_range_filter_inclusive_and_dst():
    club = _make_club("America/New_York")
    player_user = _make_user("player@test.com")
    player_mem = _make_membership(player_user, club)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)
    char = _make_character("Char", club, player_mem)

    # 2024-03-10 23:30 ET (EDT, UTC-4) = 2024-03-11 03:30 UTC
    end_day_session = _make_session(
        club, "End day", datetime(2024, 3, 11, 3, 30, tzinfo=UTC), gm_mem
    )
    # 2024-03-11 00:30 ET (EDT, UTC-4) = 2024-03-11 04:30 UTC
    next_day_session = _make_session(
        club, "Next day", datetime(2024, 3, 11, 4, 30, tzinfo=UTC), gm_mem
    )
    _make_attendance(end_day_session, char, played=True)
    _make_attendance(next_day_session, char, played=True)

    # Range end = 2024-03-10 (club-local). 23:30 ET on Mar 10 counts;
    # 00:30 ET on Mar 11 does not.
    start = date(2024, 3, 10)
    end = date(2024, 3, 10)
    characters, players = report_rows(club, start, end)

    assert len(characters) == 1
    assert characters[0]["sessions"] == 1


def test_range_filter_start_inclusive():
    club = _make_club("America/New_York")
    player_user = _make_user("player@test.com")
    player_mem = _make_membership(player_user, club)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)
    char = _make_character("Char", club, player_mem)

    session = _make_session(
        club, "Session", datetime(2024, 3, 10, 5, 0, tzinfo=UTC), gm_mem
    )  # 2024-03-10 00:00 ET
    _make_attendance(session, char, played=True)

    start = date(2024, 3, 10)
    characters, _ = report_rows(club, start, None)
    assert characters[0]["sessions"] == 1


# ---------------------------------------------------------------------------
# P8: report view (admin only, CSV link, error alert)
# ---------------------------------------------------------------------------


def test_report_view_admin_200(client):
    club = _make_club()
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    client.force_login(admin_user)

    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert b"Attendance report" in response.content


def test_report_view_player_403(client):
    club = _make_club()
    player_user = _make_user("player@test.com")
    _make_membership(player_user, club)
    client.force_login(player_user)

    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 403


def test_report_view_gm_403(client):
    club = _make_club()
    gm_user = _make_user("gm@test.com")
    _make_membership(gm_user, club, is_gm=True)
    client.force_login(gm_user)

    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 403


def test_report_view_anonymous_redirect(client):
    club = _make_club()
    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_report_view_superuser_200(client):
    club = _make_club()
    su = _make_user("su@test.com")
    su.is_superuser = True
    su.save()
    client.force_login(su)

    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 200


def test_report_view_another_club_hidden(client):
    club = _make_club()
    other_club = Club.objects.create(name="Other", slug="other-club")
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    player_user = _make_user("player@test.com")
    player_mem = _make_membership(player_user, other_club)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, other_club, is_gm=True)

    char = _make_character("Char", other_club, player_mem)
    session = _make_session(other_club, "Other Session", timezone.now(), gm_mem)
    _make_attendance(session, char, played=True)

    client.force_login(admin_user)
    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert b"Other Session" not in response.content


def test_report_view_error_alert(client):
    club = _make_club()
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    client.force_login(admin_user)

    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url, {"start": "not-a-date"})
    assert response.status_code == 200
    assert b"Not a valid" in response.content


# ---------------------------------------------------------------------------
# P8: CSV export
# ---------------------------------------------------------------------------


def test_csv_columns_and_rows(client):
    club = _make_club()
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    player_user = _make_user("player@test.com")
    player_mem = _make_membership(player_user, club)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)

    char_a = _make_character("Char A", club, player_mem)
    char_b = _make_character("Char B", club, player_mem)
    session = _make_session(club, "Session 1", timezone.now(), gm_mem)
    _make_attendance(session, char_a, played=True)
    _make_attendance(session, char_b, played=True)

    client.force_login(admin_user)
    url = reverse("play_sessions:report_csv", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    content = response.content.decode("utf-8")
    lines = content.strip().splitlines()
    assert lines[0] == "kind,name,player,sessions"
    kinds = {line.split(",")[0] for line in lines[1:]}
    assert "character" in kinds
    assert "player" in kinds


def test_csv_respects_filter(client):
    club = _make_club("America/New_York")
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    player_user = _make_user("player@test.com")
    player_mem = _make_membership(player_user, club)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)
    char = _make_character("Char", club, player_mem)

    session = _make_session(club, "Session", datetime(2024, 3, 11, 3, 30, tzinfo=UTC), gm_mem)
    _make_attendance(session, char, played=True)

    client.force_login(admin_user)
    url = reverse("play_sessions:report_csv", kwargs={"club_slug": club.slug})
    response = client.get(url, {"start": "2024-03-10", "end": "2024-03-10"})
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Char" in content


def test_csv_bad_date_400(client):
    club = _make_club()
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    client.force_login(admin_user)

    url = reverse("play_sessions:report_csv", kwargs={"club_slug": club.slug})
    response = client.get(url, {"start": "bad"})
    assert response.status_code == 400


def test_csv_formula_injection_escaped(client):
    club = _make_club()
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    player_user = _make_user("player@test.com")
    player_mem = _make_membership(player_user, club)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)

    char = _make_character("=EVIL", club, player_mem)
    session = _make_session(club, "Session", timezone.now(), gm_mem)
    _make_attendance(session, char, played=True)

    client.force_login(admin_user)
    url = reverse("play_sessions:report_csv", kwargs={"club_slug": club.slug})
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "'=EVIL" in content


# ---------------------------------------------------------------------------
# P7: sheet history
# ---------------------------------------------------------------------------


def test_sheet_history_owner_gm_admin_same_rows(client):
    club = _make_club()
    owner_user = _make_user("owner@test.com")
    owner_mem = _make_membership(owner_user, club)
    gm_user = _make_user("gm@test.com")
    _make_membership(gm_user, club, is_gm=True)
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    char = _make_character("Char", club, owner_mem)
    gm_user2 = _make_user("gm2@test.com")
    gm_mem2 = _make_membership(gm_user2, club, is_gm=True)
    session = _make_session(club, "Session 1", timezone.now(), gm_mem2)
    _make_attendance(session, char, played=True)

    url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": char.pk})

    for user in (owner_user, gm_user, admin_user):
        client.force_login(user)
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Session 1" in content
        assert "Attendance history" in content


def test_sheet_history_private_fields_absent(client):
    club = _make_club()
    owner_user = _make_user("owner@test.com")
    owner_mem = _make_membership(owner_user, club)
    _make_membership(_make_user("admin@test.com"), club, is_admin=True)
    char = _make_character("Char", club, owner_mem)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)
    session = _make_session(
        club,
        "Session",
        timezone.now(),
        gm_mem,
        location="The Tavern",
        notes="Player notes",
        recap="We fought dragons",
        gm_notes="Secret GM notes",
    )
    _make_attendance(session, char, played=True)

    client.force_login(owner_user)
    url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": char.pk})
    response = client.get(url)
    content = response.content.decode()
    assert "The Tavern" not in content
    assert "Player notes" not in content
    assert "We fought dragons" not in content
    assert "Secret GM notes" not in content


def test_sheet_history_newest_first(client):
    club = _make_club()
    owner_user = _make_user("owner@test.com")
    owner_mem = _make_membership(owner_user, club)
    char = _make_character("Char", club, owner_mem)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)

    s1 = _make_session(club, "Old", timezone.now() - timedelta(days=2), gm_mem)
    s2 = _make_session(club, "New", timezone.now() - timedelta(days=1), gm_mem)
    _make_attendance(s1, char, played=True)
    _make_attendance(s2, char, played=True)

    client.force_login(owner_user)
    url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": char.pk})
    response = client.get(url)
    content = response.content.decode()
    new_pos = content.index("New")
    old_pos = content.index("Old")
    assert new_pos < old_pos


def test_sheet_history_empty_state(client):
    club = _make_club()
    owner_user = _make_user("owner@test.com")
    owner_mem = _make_membership(owner_user, club)
    char = _make_character("Char", club, owner_mem)

    client.force_login(owner_user)
    url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": char.pk})
    response = client.get(url)
    content = response.content.decode()
    assert "No sessions played yet" in content


def test_sheet_history_no_print_wrapper(client):
    club = _make_club()
    owner_user = _make_user("owner@test.com")
    owner_mem = _make_membership(owner_user, club)
    char = _make_character("Char", club, owner_mem)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)
    session = _make_session(club, "Session", timezone.now(), gm_mem)
    _make_attendance(session, char, played=True)

    client.force_login(owner_user)
    url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": char.pk})
    response = client.get(url)
    content = response.content.decode()
    assert "no-print" in content
    assert 'data-sheet-section="attendance_history"' in content


def test_sheet_history_total_cap(client):
    club = _make_club()
    owner_user = _make_user("owner@test.com")
    owner_mem = _make_membership(owner_user, club)
    char = _make_character("Char", club, owner_mem)
    gm_user = _make_user("gm@test.com")
    gm_mem = _make_membership(gm_user, club, is_gm=True)

    for i in range(55):
        s = _make_session(club, f"Session {i}", timezone.now() - timedelta(days=i), gm_mem)
        _make_attendance(s, char, played=True)

    rows, total = sheet_history(char)
    assert total == 55
    assert len(rows) == 50


# ---------------------------------------------------------------------------
# P8: navigation
# ---------------------------------------------------------------------------


def test_nav_admin_sees_report_link(client):
    club = _make_club()
    admin_user = _make_user("admin@test.com")
    _make_membership(admin_user, club, is_admin=True)
    client.force_login(admin_user)

    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 200


def test_nav_player_no_report(client):
    club = _make_club()
    player_user = _make_user("player@test.com")
    _make_membership(player_user, club)
    client.force_login(player_user)

    url = reverse("play_sessions:report", kwargs={"club_slug": club.slug})
    response = client.get(url)
    assert response.status_code == 403
