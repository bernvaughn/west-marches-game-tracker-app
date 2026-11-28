"""Demo data for play_sessions. Safe to run more than once."""

from datetime import timedelta

from django.utils import timezone

from accounts.models import Membership
from play_sessions.core import from_club_local
from play_sessions.feed import get_or_create_token
from play_sessions.models import (
    AttendanceHint,
    PlayerRSVP,
    PlaySession,
    SessionSettings,
)
from play_sessions.services_attendance import save_attendance, set_player_rsvp


def seed(club):
    """Seed demo sessions for a club.

    Looks up sessions by (club, title) so re-runs are idempotent.
    Creates-only times are in club-local 19:00.
    """
    gm = Membership.objects.filter(club=club, user__email="gm@example.com").first()
    alice = Membership.objects.filter(club=club, user__email="alice@example.com").first()
    bob = Membership.objects.filter(club=club, user__email="bob@example.com").first()

    # Session settings: award points and calendar feed token
    settings, _ = SessionSettings.objects.get_or_create(club=club)
    if settings.award_points == 0:
        settings.award_points = 1
        settings.save(update_fields=["award_points"])
    get_or_create_token(club)

    now = timezone.now().replace(tzinfo=None)

    def club_local_19(days_from_now):
        """19:00 club-local time on the given day offset from now."""
        local = now + timedelta(days=days_from_now)
        local = local.replace(hour=19, minute=0, second=0, microsecond=0)
        return from_club_local(club, local)

    gm_user = gm.user if gm else None

    # Past sessions (with recap/attendance)
    past1_start = club_local_19(-9)
    past1_end = past1_start + timedelta(hours=3)
    session1, _ = PlaySession.objects.get_or_create(
        club=club,
        title="The Goblin Caves",
        defaults={
            "starts_at": past1_start,
            "ends_at": past1_end,
            "game_master": gm,
            "location": "The old goblin warren east of the ford",
            "recap": "The party cleared the upper warren and found a silver ring.",
            "notes": "First session of the campaign.",
        },
    )

    past2_start = club_local_19(-2)
    past2_end = past2_start + timedelta(hours=3)
    session2, _ = PlaySession.objects.get_or_create(
        club=club,
        title="Ruins of Karth",
        defaults={
            "starts_at": past2_start,
            "ends_at": past2_end,
            "game_master": gm,
            "location": "Karth ruins, three miles north",
            "recap": "",
            "notes": "Second session.",
        },
    )

    # Upcoming sessions
    upcoming1_start = club_local_19(5)
    upcoming1_end = upcoming1_start + timedelta(hours=3)
    session3, _ = PlaySession.objects.get_or_create(
        club=club,
        title="The Sunless Cellar",
        defaults={
            "starts_at": upcoming1_start,
            "ends_at": upcoming1_end,
            "game_master": gm,
            "location": "Cellar beneath the ruined manor",
            "recap": "",
            "notes": "Upcoming session.",
        },
    )

    upcoming2_start = club_local_19(12)
    upcoming2_end = upcoming2_start + timedelta(hours=3)
    session4, _ = PlaySession.objects.get_or_create(
        club=club,
        title="The Whispering Caves",
        defaults={
            "starts_at": upcoming2_start,
            "ends_at": upcoming2_end,
            "game_master": gm,
            "location": "Caves near the old well",
            "recap": "",
            "notes": "Far-future session.",
        },
    )

    # RSVPs (idempotent via update_or_create)
    if alice and bob:
        set_player_rsvp(session3, alice, PlayerRSVP.Answer.YES, gm_user)
        set_player_rsvp(session3, bob, PlayerRSVP.Answer.MAYBE, gm_user)
        set_player_rsvp(session1, alice, PlayerRSVP.Answer.YES, gm_user)
        set_player_rsvp(session1, bob, PlayerRSVP.Answer.YES, gm_user)
        set_player_rsvp(session2, alice, PlayerRSVP.Answer.YES, gm_user)
        set_player_rsvp(session2, bob, PlayerRSVP.Answer.YES, gm_user)

    # Attendance on past sessions (only when no rows exist yet)
    from player_characters.models import Character

    aria = Character.objects.filter(club=club, name="Aria Windrunner").first()
    borin = Character.objects.filter(club=club, name="Borin Stonefist").first()

    if session1.attendance.count() == 0 and aria and borin:
        save_attendance(session1, {aria.pk, borin.pk}, gm_user, club)

    if session2.attendance.count() == 0 and aria and borin:
        save_attendance(session2, {aria.pk, borin.pk}, gm_user, club)

    # Attendance hint for Wren on the upcoming +5 session
    wren = Character.objects.filter(club=club, name="Wren Thistledown").first()
    if wren:
        AttendanceHint.objects.get_or_create(session=session3, character=wren)
