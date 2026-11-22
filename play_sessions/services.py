"""Service layer for scheduling, editing, and cancelling play sessions."""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from . import core
from .models import PlaySession, SessionSeries


def occurrence_starts(club, start_date, start_time, end_time, rule, count):
    """Return a list of (starts_at, ends_at) aware UTC datetimes.

    Steps the naive local date by 7 or 14 days for each occurrence,
    then converts to UTC via core.from_club_local. This keeps the
    club clock time across DST changes.
    """
    if rule == "weekly":
        step = timedelta(days=7)
    elif rule == "every_two_weeks":
        step = timedelta(days=14)
    else:
        step = timedelta(days=0)

    occurrences = []
    for i in range(count):
        occ_date = start_date + step * i
        naive_start = datetime.combine(occ_date, start_time)
        starts_at = core.from_club_local(club, naive_start)

        if end_time is not None:
            naive_end = datetime.combine(occ_date, end_time)
            ends_at = core.from_club_local(club, naive_end)
        else:
            ends_at = None

        occurrences.append((starts_at, ends_at))

    return occurrences


@transaction.atomic
def create_sessions(club, membership, data):
    """Create one PlaySession per occurrence from form data.

    Creates a SessionSeries when repeating. Returns the list of sessions.
    """
    rule = data.get("repeat", "none")
    count = data.get("count", 1) if rule != "none" else 1

    series = None
    if rule != "none":
        series = SessionSeries.objects.create(
            club=club,
            created_by=membership,
            rule=rule,
        )

    starts_list = occurrence_starts(
        club,
        data["date"],
        data["start_time"],
        data.get("end_time"),
        rule,
        count,
    )

    sessions = []
    game_master = data.get("game_master") or membership
    for starts_at, ends_at in starts_list:
        session = PlaySession.objects.create(
            club=club,
            title=data["title"],
            starts_at=starts_at,
            ends_at=ends_at,
            game_master=game_master,
            location=data.get("location", ""),
            notes=data.get("notes", ""),
            series=series,
        )
        sessions.append(session)

    return sessions


@transaction.atomic
def update_session(session, data):
    """Edit one session row only. Series link and cancelled flag stay unchanged."""
    session.title = data["title"]
    session.starts_at = core.from_club_local(
        session.club,
        datetime.combine(data["date"], data["start_time"]),
    )
    if data.get("end_time"):
        session.ends_at = core.from_club_local(
            session.club,
            datetime.combine(data["date"], data["end_time"]),
        )
    else:
        session.ends_at = None
    session.game_master = data.get("game_master") or session.game_master
    session.location = data.get("location", "")
    session.notes = data.get("notes", "")
    session.save()
    return session


def cancel_session(session):
    """Mark a session as cancelled. The row stays. Idempotent."""
    session.cancelled = True
    session.save()
    return session


def rest_of_series(session):
    """Return the sessions that "cancel the rest" acts on, in date order.

    This session and all later uncancelled sessions of its series
    (starts_at >= this session's starts_at, so ties count as later).
    The confirm page, the Manage section and cancel_rest all use this
    one queryset, so the preview always matches the action.
    """
    if not session.series_id:
        return PlaySession.objects.none()
    return (
        PlaySession.objects.for_club(session.club)
        .filter(
            series=session.series,
            starts_at__gte=session.starts_at,
            cancelled=False,
        )
        .order_by("starts_at", "pk")
    )


def cancel_rest(session):
    """Cancel this and all later uncancelled sessions in the series.

    Sets updated=now explicitly because QuerySet.update() skips auto_now.
    Returns the count of sessions cancelled.
    """
    # update() cannot run on an ordered, sliced queryset safely; clear ordering.
    return rest_of_series(session).order_by().update(cancelled=True, updated=timezone.now())
