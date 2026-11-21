import pytest
from datetime import timezone as dt_timezone
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Club
from play_sessions import core
from play_sessions.models import (
    SessionSeries,
    PlaySession,
    SessionRSVP,
    SessionAttendance,
    AttendanceChange,
    SessionAward,
    SessionSettings,
)


pytestmark = [pytest.mark.django_db, pytest.mark.story("P1")]


def test_app_label_and_installed():
    assert apps.get_app_config("play_sessions").label == "play_sessions"
    assert "play_sessions" in settings.INSTALLED_APPS


def test_all_models_have_club_path_and_manager():
    for model in [
        SessionSeries,
        PlaySession,
        SessionRSVP,
        SessionAttendance,
        AttendanceChange,
        SessionAward,
        SessionSettings,
    ]:
        assert hasattr(model, "club_path"), f"{model.__name__} missing club_path"
        assert hasattr(model, "objects"), f"{model.__name__} missing objects"
        # ClubScopedManager provides for_club
        assert hasattr(model.objects, "for_club"), f"{model.__name__} manager missing for_club"


def test_unique_constraints():
    club = Club.objects.create(name="Test Club", slug="test-club")
    from accounts.models import Membership, User
    from player_characters.models import Character

    user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    membership = Membership.objects.create(user=user, club=club, is_game_master=True)
    character = Character.objects.create(name="Hero", club=club, owner=membership)

    series = SessionSeries.objects.create(club=club, rule=SessionSeries.Rule.WEEKLY, created_by=membership)
    session = PlaySession.objects.create(
        club=club, title="Session 1", starts_at=timezone.now(), game_master=membership, series=series
    )

    # Unique session + character for RSVP
    SessionRSVP.objects.create(session=session, character=character, answer=SessionRSVP.Answer.YES)
    with pytest.raises(IntegrityError):
        SessionRSVP.objects.create(session=session, character=character, answer=SessionRSVP.Answer.NO)

    # Unique session + character for Attendance
    SessionAttendance.objects.create(session=session, character=character, played=True)
    with pytest.raises(IntegrityError):
        SessionAttendance.objects.create(session=session, character=character, played=False)

    # Unique session + character for Award
    SessionAward.objects.create(session=session, character=character, points=5)
    with pytest.raises(IntegrityError):
        SessionAward.objects.create(session=session, character=character, points=3)

    # SessionSettings one-to-one
    SessionSettings.objects.create(club=club, award_points=2)
    with pytest.raises(IntegrityError):
        SessionSettings.objects.create(club=club, award_points=3)


def test_attendance_change_append_only():
    club = Club.objects.create(name="Test Club", slug="test-club-2")
    from accounts.models import Membership, User
    from player_characters.models import Character

    user = User.objects.create_user(email="gm2@test.com", password="pass12345678")
    membership = Membership.objects.create(user=user, club=club, is_game_master=True)
    character = Character.objects.create(name="Hero2", club=club, owner=membership)
    session = PlaySession.objects.create(club=club, title="Session 2", starts_at=timezone.now(), game_master=membership)

    change = AttendanceChange.objects.create(
        session=session, character=character, old_played=None, new_played=True, changed_by=user
    )

    # Update should raise
    with pytest.raises(Exception) as exc:
        AttendanceChange.objects.filter(pk=change.pk).update(new_played=False)
    assert "cannot be updated" in str(exc.value).lower()

    # Delete should raise
    with pytest.raises(Exception) as exc:
        AttendanceChange.objects.filter(pk=change.pk).delete()
    assert "cannot be deleted" in str(exc.value).lower()

    # Instance save should raise
    with pytest.raises(Exception) as exc:
        change.new_played = False
        change.save()
    assert "cannot be changed" in str(exc.value).lower()

    # Instance delete should raise
    with pytest.raises(Exception) as exc:
        change.delete()
    assert "cannot be deleted" in str(exc.value).lower()


def test_club_timezone_default_and_validation():
    club = Club.objects.create(name="Test Club 3", slug="test-club-3")
    assert club.timezone == settings.TIME_ZONE

    # Bad timezone should fail full_clean
    club2 = Club(name="Test Club 4", slug="test-club-4", timezone="Not/A/Timezone")
    with pytest.raises(ValidationError):
        club2.full_clean()


def test_moment_stored_utc_shown_in_club_zone_across_dst():
    """A moment stored in UTC is shown in the club zone correctly across DST change."""
    club = Club.objects.create(name="NY Club", slug="ny-club", timezone="America/New_York")
    from accounts.models import Membership, User
    from player_characters.models import Character

    user = User.objects.create_user(email="gm3@test.com", password="pass12345678")
    membership = Membership.objects.create(user=user, club=club, is_game_master=True)

    # March 9, 2024 19:00 EST (UTC-5) -> 2024-03-10 00:00 UTC
    starts_est = timezone.datetime(2024, 3, 10, 0, 0, tzinfo=dt_timezone.utc)
    session1 = PlaySession.objects.create(
        club=club, title="Before DST", starts_at=starts_est, game_master=membership
    )
    local1 = core.to_club_local(club, session1.starts_at)
    assert local1.utcoffset().total_seconds() == -5 * 3600
    assert local1.hour == 19

    # March 10, 2024 19:00 EDT (UTC-4) -> 2024-03-10 23:00 UTC
    starts_edt = timezone.datetime(2024, 3, 10, 23, 0, tzinfo=dt_timezone.utc)
    session2 = PlaySession.objects.create(
        club=club, title="After DST", starts_at=starts_edt, game_master=membership
    )
    local2 = core.to_club_local(club, session2.starts_at)
    assert local2.utcoffset().total_seconds() == -4 * 3600
    assert local2.hour == 19


def test_changing_club_zone_keeps_moment_changes_display():
    """Changing the club timezone keeps the stored UTC moment but changes local display."""
    club = Club.objects.create(name="Zone Club", slug="zone-club", timezone="America/New_York")
    from accounts.models import Membership, User
    from player_characters.models import Character

    user = User.objects.create_user(email="gm4@test.com", password="pass12345678")
    membership = Membership.objects.create(user=user, club=club, is_game_master=True)

    utc_moment = timezone.datetime(2024, 6, 15, 12, 0, tzinfo=dt_timezone.utc)
    session = PlaySession.objects.create(
        club=club, title="Zone Test", starts_at=utc_moment, game_master=membership
    )

    # Display in NY (EDT, UTC-4)
    local_ny = core.to_club_local(club, session.starts_at)
    assert local_ny.hour == 8  # 12:00 UTC = 08:00 EDT

    # Change club to Los Angeles (PDT, UTC-7)
    club.timezone = "America/Los_Angeles"
    club.save()

    local_la = core.to_club_local(club, session.starts_at)
    assert local_la.hour == 5  # 12:00 UTC = 05:00 PDT

    # Stored moment unchanged
    session.refresh_from_db()
    assert session.starts_at == utc_moment


def test_feed_token_blank_allowed_in_multiple_clubs():
    """Multiple clubs can have blank feed_token (conditional unique constraint)."""
    club1 = Club.objects.create(name="Club 1", slug="club-1")
    club2 = Club.objects.create(name="Club 2", slug="club-2")

    SessionSettings.objects.create(club=club1, award_points=1, feed_token="")
    SessionSettings.objects.create(club=club2, award_points=2, feed_token="")  # Should not raise

    # But non-blank tokens must be unique
    SessionSettings.objects.filter(club=club1).update(feed_token="abc123")
    with pytest.raises(IntegrityError):
        SessionSettings.objects.filter(club=club2).update(feed_token="abc123")