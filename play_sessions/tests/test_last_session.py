"""Tests for the 'Last session' dashboard card (P22)."""

from datetime import UTC, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import last_session
from play_sessions.models import PlaySession, SessionAttendance
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("P22")]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def club_and_data():
    club = Club.objects.create(name="Test Club", slug="test-club", timezone="America/New_York")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    player2_user = User.objects.create_user(email="player2@test.com", password="pass12345678")

    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    player_membership = Membership.objects.create(user=player_user, club=club)
    player2_membership = Membership.objects.create(user=player2_user, club=club)

    char1 = Character.objects.create(name="Aria Windrunner", club=club, owner=player_membership)
    char2 = Character.objects.create(name="Borin Stonefist", club=club, owner=player_membership)
    char3 = Character.objects.create(name="Other Hero", club=club, owner=player2_membership)

    return {
        "club": club,
        "gm_user": gm_user,
        "gm_membership": gm_membership,
        "player_user": player_user,
        "player_membership": player_membership,
        "player2_user": player2_user,
        "player2_membership": player2_membership,
        "char1": char1,
        "char2": char2,
        "char3": char3,
    }


def _make_session(
    club, gm_membership, starts_at, ends_at=None, cancelled=False, recap="", gm_notes=""
):
    return PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=starts_at,
        ends_at=ends_at,
        game_master=gm_membership,
        recap=recap,
        gm_notes=gm_notes,
        cancelled=cancelled,
    )


# ---------------------------------------------------------------------------
# Core logic tests (last_session.build)
# ---------------------------------------------------------------------------


def test_build_returns_none_when_no_session_ended(club_and_data):
    """No session has ended -> None."""
    club = club_and_data["club"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    result = last_session.build(club, membership, char, now)
    assert result is None


def test_build_returns_none_when_only_future_session(club_and_data):
    """Only a future session exists -> None."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    _make_session(club, gm_membership, timezone.datetime(2024, 6, 15, 18, 0, tzinfo=UTC))
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    result = last_session.build(club, membership, char, now)
    assert result is None


def test_build_returns_none_when_only_cancelled_session(club_and_data):
    """Only a cancelled session exists -> None."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        cancelled=True,
    )
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    result = last_session.build(club, membership, char, now)
    assert result is None


def test_build_returns_none_for_foreign_club_session(club_and_data):
    """Session from another club doesn't count -> None."""
    club = club_and_data["club"]
    club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    other_club = Club.objects.create(name="Other", slug="other")
    other_gm = Membership.objects.create(
        user=club_and_data["gm_user"], club=other_club, is_game_master=True
    )
    _make_session(other_club, other_gm, timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC))

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    result = last_session.build(club, membership, char, now)
    assert result is None


def test_latest_ended_session_wins_over_older(club_and_data):
    """Latest ended session is returned, not older ones."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 1, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 1, 22, 0, tzinfo=UTC),
        recap="Older recap",
    )
    _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Newer recap",
    )
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    result = last_session.build(club, membership, char, now)
    assert result is not None
    assert result["session"]["title"] == "Test Session"
    assert result["session"]["recap"] == "Newer recap"


def test_cancelled_sessions_are_skipped(club_and_data):
    """Cancelled sessions are ignored even if they are the latest."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 20, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 20, 22, 0, tzinfo=UTC),
        cancelled=True,
        recap="Cancelled recap",
    )
    _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Good recap",
    )
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    result = last_session.build(club, membership, char, now)
    assert result is not None
    assert result["session"]["recap"] == "Good recap"


def test_played_as_selected_character(club_and_data):
    """When selected character played, shows their name."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char1 = club_and_data["char1"]
    char2 = club_and_data["char2"]

    session = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Session recap",
    )
    SessionAttendance.objects.create(session=session, character=char1, played=True)
    SessionAttendance.objects.create(session=session, character=char2, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char1, now)

    assert result["played_as"] == "Aria Windrunner"


def test_played_as_other_character_when_selected_did_not_play(club_and_data):
    """When selected character didn't play but another did, shows the other."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char1 = club_and_data["char1"]
    char2 = club_and_data["char2"]

    session = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Session recap",
    )
    SessionAttendance.objects.create(session=session, character=char1, played=False)
    SessionAttendance.objects.create(session=session, character=char2, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char1, now)

    assert result["played_as"] == "Borin Stonefist"


def test_did_not_play_when_no_attendance(club_and_data):
    """No attendance row -> 'You did not play'."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Session recap",
    )
    # No attendance rows at all
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["played_as"] is None


def test_did_not_play_when_played_false(club_and_data):
    """Attendance with played=False -> 'You did not play'."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    session = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Session recap",
    )
    SessionAttendance.objects.create(session=session, character=char, played=False)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["played_as"] is None


def test_tally_counts_only_played_true_ended_noncancelled(club_and_data):
    """Tally counts only played=True on ended, non-cancelled sessions."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    # Ended, played
    s1 = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 1, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 1, 22, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s1, character=char, played=True)

    # Ended, not played
    s2 = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 8, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 8, 22, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s2, character=char, played=False)

    # Cancelled, played
    s3 = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        cancelled=True,
    )
    SessionAttendance.objects.create(session=s3, character=char, played=True)

    # Future, played
    s4 = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 6, 15, 18, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s4, character=char, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["tally"] == 1


def test_tally_zero_when_character_none(club_and_data):
    """Tally is 0 when character is None."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]

    _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Session recap",
    )
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, None, now)

    assert result["tally"] == 0


# ---------------------------------------------------------------------------
# Milestone tests
# ---------------------------------------------------------------------------


def test_milestones_earned_at_thresholds(club_and_data):
    """Milestones earned at 1, 5, 10, 25."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    # Create 5 ended sessions with played=True
    for i in range(5):
        s = _make_session(
            club,
            gm_membership,
            timezone.datetime(2024, 5, 1 + i * 7, 18, 0, tzinfo=UTC),
            timezone.datetime(2024, 5, 1 + i * 7, 22, 0, tzinfo=UTC),
        )
        SessionAttendance.objects.create(session=s, character=char, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    milestones = result["milestones"]
    assert milestones[0]["earned"] is True  # 1
    assert milestones[1]["earned"] is True  # 5
    assert milestones[2]["earned"] is False  # 10
    assert milestones[3]["earned"] is False  # 25


def test_milestones_labels_correct(club_and_data):
    """Milestone labels match spec."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    s = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s, character=char, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["milestones"][0]["label"] == "First steps"
    assert result["milestones"][1]["label"] == "Regular"
    assert result["milestones"][2]["label"] == "Veteran"
    assert result["milestones"][3]["label"] == "Legend"


def test_new_mark_on_day_of_session(club_and_data):
    """'New' mark shows on the day the milestone was reached."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    s = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s, character=char, played=True)

    # Same day as session ended
    now = timezone.datetime(2024, 5, 15, 23, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["milestones"][0]["is_new"] is True


def test_new_mark_still_shows_on_day_7(club_and_data):
    """'New' mark still shows on day 7 after the session (at the same time)."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    s = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s, character=char, played=True)

    # 7 days later at same time (still within 7 days)
    now = timezone.datetime(2024, 5, 22, 22, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["milestones"][0]["is_new"] is True


def test_new_mark_gone_on_day_8(club_and_data):
    """'New' mark is gone on day 8 after the session."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    s = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s, character=char, played=True)

    # 8 days later (outside 7 days)
    now = timezone.datetime(2024, 5, 23, 0, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["milestones"][0]["is_new"] is False


def test_new_mark_per_milestone_independent(club_and_data):
    """Each milestone has its own 'New' mark based on when it was reached."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    # Create 5 sessions - the 5th reaches "Regular" milestone
    for i in range(5):
        s = _make_session(
            club,
            gm_membership,
            timezone.datetime(2024, 5, 1 + i * 7, 18, 0, tzinfo=UTC),
            timezone.datetime(2024, 5, 1 + i * 7, 22, 0, tzinfo=UTC),
        )
        SessionAttendance.objects.create(session=s, character=char, played=True)

    # On the day the 5th session ended:
    # - 1st milestone (session 1, May 1) is 28 days old -> NOT new
    # - 5th milestone (session 5, May 29) is just reached -> IS new
    now = timezone.datetime(2024, 5, 29, 23, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["milestones"][0]["is_new"] is False  # First steps reached 28 days ago
    assert result["milestones"][1]["is_new"] is True  # Regular reached today


def test_later_milestone_does_not_clear_earlier_new(club_and_data):
    """A later milestone being reached doesn't clear an earlier one still within 7 days."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    # Session 1: 20 days ago (First steps, not new)
    s1 = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 1, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 1, 22, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s1, character=char, played=True)

    # Session 5: today (Regular, new)
    s5 = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 29, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 29, 22, 0, tzinfo=UTC),
    )
    SessionAttendance.objects.create(session=s5, character=char, played=True)

    # Fill sessions 2, 3, 4
    for i in range(2, 5):
        s = _make_session(
            club,
            gm_membership,
            timezone.datetime(2024, 5, 1 + (i - 1) * 7, 18, 0, tzinfo=UTC),
            timezone.datetime(2024, 5, 1 + (i - 1) * 7, 22, 0, tzinfo=UTC),
        )
        SessionAttendance.objects.create(session=s, character=char, played=True)

    now = timezone.datetime(2024, 5, 29, 23, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["milestones"][0]["is_new"] is False  # First steps reached 28 days ago
    assert result["milestones"][1]["is_new"] is True  # Regular reached today


def test_next_milestone_shows_remaining(club_and_data):
    """Next milestone shows remaining sessions to reach it."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    # 3 sessions played
    for i in range(3):
        s = _make_session(
            club,
            gm_membership,
            timezone.datetime(2024, 5, 1 + i * 7, 18, 0, tzinfo=UTC),
            timezone.datetime(2024, 5, 1 + i * 7, 22, 0, tzinfo=UTC),
        )
        SessionAttendance.objects.create(session=s, character=char, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    result = last_session.build(club, membership, char, now)

    assert result["next_milestone"]["label"] == "Regular"
    assert result["next_milestone"]["remaining"] == 2


def test_next_milestone_none_after_legend(club_and_data):
    """Next milestone is None after Legend (25)."""
    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    # 25 sessions played - use timedelta to avoid month overflow
    base = timezone.datetime(2024, 1, 1, 18, 0, tzinfo=UTC)
    for i in range(25):
        starts = base + timedelta(days=i * 7)
        ends = starts + timedelta(hours=4)
        s = _make_session(club, gm_membership, starts, ends)
        SessionAttendance.objects.create(session=s, character=char, played=True)

    now = base + timedelta(days=25 * 7 + 1)
    result = last_session.build(club, membership, char, now)

    assert result["next_milestone"] is None


# ---------------------------------------------------------------------------
# Dashboard integration tests
# ---------------------------------------------------------------------------


def test_dashboard_renders_last_session_card(club_and_data, client):
    """Dashboard shows the last session card with recap."""
    club = club_and_data["club"]
    player_user = club_and_data["player_user"]
    club_and_data["player_membership"]
    gm_membership = club_and_data["gm_membership"]
    char = club_and_data["char1"]

    session = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Session recap text here.",
    )
    SessionAttendance.objects.create(session=session, character=char, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(timezone, "now", lambda: now)
        client.force_login(player_user)
        url = reverse("accounts:player_dashboard", args=[club.slug])
        response = client.get(url)

    assert response.status_code == 200
    assert b"Last session" in response.content
    assert b"Session recap text here." in response.content
    assert b"You played as <strong>Aria Windrunner</strong>." in response.content
    assert b"1 session played." in response.content
    assert b"First steps" in response.content


def test_dashboard_no_gm_notes_in_html(club_and_data, client):
    """gm_notes never appears in the dashboard card HTML."""
    club = club_and_data["club"]
    player_user = club_and_data["player_user"]
    club_and_data["player_membership"]
    gm_membership = club_and_data["gm_membership"]
    char = club_and_data["char1"]

    session = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Session recap",
        gm_notes="Secret GM notes here.",
    )
    SessionAttendance.objects.create(session=session, character=char, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(timezone, "now", lambda: now)
        client.force_login(player_user)
        url = reverse("accounts:player_dashboard", args=[club.slug])
        response = client.get(url)

    assert response.status_code == 200
    assert b"Secret GM notes here." not in response.content
    assert b"GM notes" not in response.content


def test_dashboard_no_inline_style_in_card(club_and_data, client):
    """Card has no inline style attribute."""
    club = club_and_data["club"]
    player_user = club_and_data["player_user"]
    club_and_data["player_membership"]
    gm_membership = club_and_data["gm_membership"]
    char = club_and_data["char1"]

    session = _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
        recap="Session recap",
    )
    SessionAttendance.objects.create(session=session, character=char, played=True)

    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(timezone, "now", lambda: now)
        client.force_login(player_user)
        url = reverse("accounts:player_dashboard", args=[club.slug])
        response = client.get(url)

    assert response.status_code == 200
    # Check that there's no style= attribute inside the last-session card
    html = response.content.decode()
    # Find the last-session card and verify no style attribute
    card_start = html.find('id="dashboard-card-last_session"')
    assert card_start >= 0
    card_end = html.find("</div>", card_start)
    card_html = html[card_start:card_end]
    assert "style=" not in card_html


def test_dashboard_card_absent_when_no_session_ended(club_and_data, client):
    """Card is not rendered when no session has ended."""
    club = club_and_data["club"]
    player_user = club_and_data["player_user"]
    club_and_data["player_membership"]
    club_and_data["char1"]

    # No sessions at all
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(timezone, "now", lambda: now)
        client.force_login(player_user)
        url = reverse("accounts:player_dashboard", args=[club.slug])
        response = client.get(url)

    assert response.status_code == 200
    assert b"Last session" not in response.content
    assert b"dashboard-card-last_session" not in response.content


def test_provider_should_show_false_when_no_ended_session(club_and_data):
    """Provider's should_show returns False when no ended session."""
    from django.test import RequestFactory

    from play_sessions.hooks_recap import LastSessionProvider

    club = club_and_data["club"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    factory = RequestFactory()
    request = factory.get("/")
    request.club = club

    provider = LastSessionProvider()
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(timezone, "now", lambda: now)
        assert provider.should_show(request, club, char, membership) is False


def test_provider_should_show_true_when_ended_session_exists(club_and_data):
    """Provider's should_show returns True when ended session exists."""
    from django.test import RequestFactory

    from play_sessions.hooks_recap import LastSessionProvider

    club = club_and_data["club"]
    gm_membership = club_and_data["gm_membership"]
    membership = club_and_data["player_membership"]
    char = club_and_data["char1"]

    _make_session(
        club,
        gm_membership,
        timezone.datetime(2024, 5, 15, 18, 0, tzinfo=UTC),
        timezone.datetime(2024, 5, 15, 22, 0, tzinfo=UTC),
    )

    factory = RequestFactory()
    request = factory.get("/")
    request.club = club

    provider = LastSessionProvider()
    now = timezone.datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(timezone, "now", lambda: now)
        assert provider.should_show(request, club, char, membership) is True


# ---------------------------------------------------------------------------
# CSS check
# ---------------------------------------------------------------------------


def test_css_has_print_hide_rule():
    """CSS file contains print-hide rule for .last-session."""
    css_path = "static/css/sessions.css"
    with open(css_path) as f:
        content = f.read()

    assert "@media print" in content
    assert ".last-session { display: none !important; }" in content
