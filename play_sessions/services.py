"""Service layer for scheduling, editing, and cancelling play sessions."""

from datetime import datetime

from django.db import transaction

from . import core
from .models import PlaySession


@transaction.atomic
def create_sessions(club, membership, data):
    """Create exactly one PlaySession from form data.

    Returns a list with the single created session (for API compatibility).
    """
    starts_at = core.from_club_local(
        club,
        datetime.combine(data["date"], data["start_time"]),
    )
    if data.get("end_time"):
        ends_at = core.from_club_local(
            club,
            datetime.combine(data["date"], data["end_time"]),
        )
    else:
        ends_at = None

    game_master = data.get("game_master") or membership
    session = PlaySession.objects.create(
        club=club,
        title=data["title"],
        starts_at=starts_at,
        ends_at=ends_at,
        game_master=game_master,
        location=data.get("location", ""),
        notes=data.get("notes", ""),
    )
    return [session]


@transaction.atomic
def update_session(session, data):
    """Edit one session row only."""
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
