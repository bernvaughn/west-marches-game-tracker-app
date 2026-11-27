"""Logic for the 'Last session' dashboard card.

Pure functions with no request or template code.
"""

from datetime import timedelta

from django.db.models import Q
from django.urls import reverse

from play_sessions.core import to_club_local
from play_sessions.models import PlaySession, SessionAttendance

MILESTONES = ((1, "First steps"), (5, "Regular"), (10, "Veteran"), (25, "Legend"))
NEW_DAYS = 7


def ended_sessions(club, now):
    """Return queryset of ended, non-cancelled sessions for a club.

    A session counts as ended when:
    - ends_at <= now, OR
    - ends_at is null AND starts_at <= now
    """
    return (
        PlaySession.objects.for_club(club)
        .filter(cancelled=False)
        .filter(Q(ends_at__lte=now) | Q(ends_at__isnull=True, starts_at__lte=now))
    )


def latest_ended_session(club, now):
    """Return the most recent ended session for a club, or None."""
    return ended_sessions(club, now).order_by("-starts_at", "-id").first()


def played_sessions(character, now):
    """Return the character's attended sessions with played=True on ended sessions.

    Ordered by session starts_at, then id.
    """
    ended = ended_sessions(character.club, now).values_list("pk", flat=True)
    return (
        SessionAttendance.objects.filter(character=character, session__in=ended, played=True)
        .select_related("session")
        .order_by("session__starts_at", "session__id")
    )


def reached_at(session):
    """Return the datetime when the session is considered reached.

    Uses ends_at if present, otherwise starts_at.
    """
    return session.ends_at or session.starts_at


def build(club, membership, character, now):
    """Build context for the last session dashboard card.

    Returns None when no session has ended.
    """
    session = latest_ended_session(club, now)
    if session is None:
        return None

    # Check if the member played at this session with any character
    member_played = SessionAttendance.objects.filter(
        session=session, character__owner=membership, played=True
    ).select_related("character")

    # Prefer the selected character if they played
    played_as = None
    if character:
        played_attendance = member_played.filter(character=character).first()
        if played_attendance:
            played_as = character.name
    if played_as is None:
        # Fall back to any character the member played
        first_played = member_played.first()
        if first_played:
            played_as = first_played.character.name

    # Tally: count of sessions the selected character played
    if character:
        tally = played_sessions(character, now).count()
    else:
        tally = 0

    # Milestones
    played_list = list(played_sessions(character, now)) if character else []
    milestones = []
    for count, label in MILESTONES:
        earned = tally >= count
        is_new = False
        if earned and played_list:
            # The session that reached this milestone is the (count-1)th index
            milestone_session = played_list[count - 1]
            reached = reached_at(milestone_session.session)
            if now - reached <= timedelta(days=NEW_DAYS):
                is_new = True
        milestones.append(
            {
                "count": count,
                "label": label,
                "earned": earned,
                "is_new": is_new,
            }
        )

    # Next milestone
    next_milestone = None
    for count, label in MILESTONES:
        if tally < count:
            next_milestone = {"label": label, "remaining": count - tally}
            break

    # Session detail URL
    detail_url = reverse(
        "play_sessions:session_detail",
        kwargs={"club_slug": club.slug, "pk": session.pk},
    )

    return {
        "session": {
            "title": session.title,
            "local_start": to_club_local(club, session.starts_at) if session.starts_at else None,
            "detail_url": detail_url,
            "recap": session.recap,
        },
        "played_as": played_as,
        "tally": tally,
        "milestones": milestones,
        "next_milestone": next_milestone,
    }
