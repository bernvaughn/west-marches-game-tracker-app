"""Builders for session reminder, cancel, and change emails (E5)."""

from mail.builders import render_email
from play_sessions.core import to_club_local


def build_reminder(club, session, days: int, membership=None) -> tuple[str, str, str]:
    """Build the session reminder email content.

    Args:
        club: Club instance.
        session: PlaySession instance.
        days: Number of days before the session.
        membership: Membership the reminder is addressed to (player-level email).

    Returns:
        Tuple of (subject, text, html).
    """
    local_start = to_club_local(club, session.starts_at)
    local_end = to_club_local(club, session.ends_at) if session.ends_at else None

    gm_name = (
        session.game_master.user.display_name
        if session.game_master and session.game_master.user.display_name
        else (session.game_master.user.email if session.game_master else "TBA")
    )

    context = {
        "club": club,
        "session": session,
        "local_start": local_start,
        "local_end": local_end,
        "days": days,
        "gm_name": gm_name,
        "location": session.location or "Not specified",
        "membership": membership,
        "user": membership.user if membership is not None else None,
        "subject": f"Reminder: {session.title}",
    }

    return render_email("reminder", "session_reminder", context, club)


def build_cancelled(club, session) -> tuple[str, str, str]:
    """Build the session cancelled email content.

    Args:
        club: Club instance.
        session: PlaySession instance.

    Returns:
        Tuple of (subject, text, html).
    """
    local_start = to_club_local(club, session.starts_at)
    local_end = to_club_local(club, session.ends_at) if session.ends_at else None

    gm_name = (
        session.game_master.user.display_name
        if session.game_master and session.game_master.user.display_name
        else (session.game_master.user.email if session.game_master else "TBA")
    )

    context = {
        "club": club,
        "session": session,
        "local_start": local_start,
        "local_end": local_end,
        "gm_name": gm_name,
        "location": session.location or "Not specified",
        "subject": f"Session cancelled: {session.title}",
    }

    return render_email("cancel", "session_cancelled", context, club)


def build_changed(club, session, old_start, new_start) -> tuple[str, str, str]:
    """Build the session changed email content.

    Args:
        club: Club instance.
        session: PlaySession instance.
        old_start: Old starts_at datetime (UTC).
        new_start: New starts_at datetime (UTC).

    Returns:
        Tuple of (subject, text, html).
    """
    local_old_start = to_club_local(club, old_start)
    local_new_start = to_club_local(club, new_start)
    local_new_end = to_club_local(club, session.ends_at) if session.ends_at else None

    gm_name = (
        session.game_master.user.display_name
        if session.game_master and session.game_master.user.display_name
        else (session.game_master.user.email if session.game_master else "TBA")
    )

    context = {
        "club": club,
        "session": session,
        "local_old_start": local_old_start,
        "local_new_start": local_new_start,
        "local_new_end": local_new_end,
        "gm_name": gm_name,
        "location": session.location or "Not specified",
        "subject": f"Session changed: {session.title}",
    }

    return render_email("change", "session_changed", context, club)
