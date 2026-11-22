"""Attendance report queries for the play_sessions app.

Pure query code: no request objects, no HTTP. All dates are club-local
and inclusive; stored instants are UTC. The club time zone keeps a
late-evening session on the right local day across DST changes.
"""

from datetime import date, datetime, time, timedelta

from django.db.models import Count

from . import core
from .models import SessionAttendance


def parse_range(params, club):
    """Parse GET ``start`` / ``end`` (ISO YYYY-MM-DD, club-local, inclusive).

    Returns ``(start_date | None, end_date | None, error | None)``.
    Blank means unbounded. A bad date or ``end < start`` returns an error
    string with both dates unset (empty report).
    """
    start = None
    end = None
    error = None

    start_str = (params.get("start") or "").strip()
    end_str = (params.get("end") or "").strip()

    if start_str:
        try:
            start = date.fromisoformat(start_str)
        except ValueError:
            error = f"Not a valid start date: {start_str}"
    if end_str and not error:
        try:
            end = date.fromisoformat(end_str)
        except ValueError:
            error = f"Not a valid end date: {end_str}"
    if start and end and end < start and not error:
        error = "End date must be on or after the start date."

    if error:
        return None, None, error
    return start, end, None


def range_bounds(club, start, end):
    """Convert club-local inclusive dates to UTC bounds.

    Returns ``(utc_from | None, utc_to | None)`` for use as
    ``starts_at__gte`` / ``starts_at__lt``.
    """
    utc_from = None
    utc_to = None
    if start is not None:
        utc_from = core.from_club_local(club, datetime.combine(start, time.min))
    if end is not None:
        utc_to = core.from_club_local(club, datetime.combine(end + timedelta(days=1), time.min))
    return utc_from, utc_to


def played_qs(club, utc_from, utc_to):
    """Return played, non-cancelled attendance rows for the club in range."""
    qs = SessionAttendance.objects.for_club(club).filter(played=True, session__cancelled=False)
    if utc_from is not None:
        qs = qs.filter(session__starts_at__gte=utc_from)
    if utc_to is not None:
        qs = qs.filter(session__starts_at__lt=utc_to)
    return qs


def _owner_display(display_name, email):
    """Return a membership owner's display name or email."""
    return display_name or email


def character_rows(qs):
    """Group played sessions by character: name, owner, distinct session count."""
    data = (
        qs.values(
            "character_id",
            "character__name",
            "character__owner__user__display_name",
            "character__owner__user__email",
        )
        .annotate(sessions=Count("session_id", distinct=True))
        .order_by("-sessions", "character__name")
    )
    rows = []
    for item in data:
        rows.append(
            {
                "character_id": item["character_id"],
                "name": item["character__name"],
                "owner": _owner_display(
                    item["character__owner__user__display_name"],
                    item["character__owner__user__email"],
                ),
                "sessions": item["sessions"],
            }
        )
    return rows


def player_rows(qs):
    """Group played sessions by player: name, distinct session count.

    ``distinct=True`` makes a player count once per session even when two
    of their characters attended.
    """
    data = (
        qs.values(
            "character__owner_id",
            "character__owner__user__display_name",
            "character__owner__user__email",
        )
        .annotate(sessions=Count("session_id", distinct=True))
        .order_by("-sessions", "character__owner__user__display_name")
    )
    rows = []
    for item in data:
        rows.append(
            {
                "owner_id": item["character__owner_id"],
                "name": _owner_display(
                    item["character__owner__user__display_name"],
                    item["character__owner__user__email"],
                ),
                "sessions": item["sessions"],
            }
        )
    return rows


def report_rows(club, start, end):
    """Return ``(character_rows, player_rows)`` for the club in the date range."""
    utc_from, utc_to = range_bounds(club, start, end)
    qs = played_qs(club, utc_from, utc_to)
    return character_rows(qs), player_rows(qs)


def sheet_history(character):
    """Return ``(rows, total)`` of a character's played sessions, newest first.

    Rows are capped at 50. Each row holds the local date, session title,
    GM name, and session id. Private fields (location, notes, recap,
    gm_notes, RSVPs, awards) are never read.
    """
    qs = (
        SessionAttendance.objects.for_club(character.club)
        .filter(character=character, played=True, session__cancelled=False)
        .select_related("session", "session__game_master__user")
        .order_by("-session__starts_at")
    )
    total = qs.count()
    rows = []
    for a in qs[:50]:
        local = core.to_club_local(character.club, a.session.starts_at)
        gm = a.session.game_master
        gm_name = ""
        if gm is not None:
            gm_name = gm.user.display_name or gm.user.email
        rows.append(
            {
                "date": local.date(),
                "title": a.session.title,
                "gm": gm_name,
                "session_id": a.session.pk,
            }
        )
    return rows, total
