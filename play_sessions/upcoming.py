"""Shared upcoming-sessions query.

Every screen that lists upcoming sessions uses this single query so they
cannot disagree about what counts as "upcoming".

``now`` must be an aware datetime (normally UTC). The club-local day of
"now" decides start-of-today in the club time zone.
"""

from datetime import datetime, time

from django.db.models import Count, Q
from django.urls import reverse

from . import core
from .models import PlayerRSVP, PlaySession


def _when_text(delta_days: int) -> str:
    """Club-local calendar day wording for the next session."""
    if delta_days <= 0:
        return "today"
    if delta_days == 1:
        return "tomorrow"
    if delta_days < 14:
        return f"in {delta_days} days"
    return f"in {delta_days // 7} weeks"


def upcoming_sessions(club, now, membership, limit):
    """Return the club's upcoming sessions plus ``first_month``.

    "Upcoming" means the session's club-local day is today or later, where
    today is computed in the club time zone via :func:`core.club_zone` and
    :func:`core.from_club_local`. A session counts while
    ``starts_at >= start_of_today`` OR ``ends_at >= start_of_today``, so a
    7 PM session stays listed through the local evening and a session that
    ends after midnight counts through the day it ends.

    Cancelled sessions are included. Results are ordered by ``starts_at``
    then id and ``limit`` applies to the whole list.

    ``yes_count`` is annotated from ``player_rsvps`` (answer "yes") and the
    member's own answer is read from ``PlayerRSVP`` in one query for all
    rows.

    Returns ``{"sessions": [...], "first_month": (year, month) | None}``.
    Each session dict holds id, title, local_start, zone_label, gm_name,
    yes_count, my_answer, cancelled, can_rsvp, detail_url, is_next,
    when_text. ``can_rsvp`` is true only for non-cancelled sessions that
    have not started yet (``starts_at > now``).
    """
    zone = core.club_zone(club)
    now_local = core.to_club_local(club, now)
    today = now_local.date()
    start_of_today_utc = core.from_club_local(club, datetime.combine(today, time.min))

    qs = (
        PlaySession.objects.for_club(club)
        .filter(Q(starts_at__gte=start_of_today_utc) | Q(ends_at__gte=start_of_today_utc))
        .select_related("game_master__user")
        .annotate(yes_count=Count("player_rsvps", filter=Q(player_rsvps__answer="yes")))
        .order_by("starts_at", "id")
    )
    if limit is not None:
        qs = qs[:limit]
    sessions = list(qs)

    # One query for the member's own answers across all returned rows.
    my_answers = {}
    if membership is not None:
        my_rsvps = PlayerRSVP.objects.filter(
            session_id__in=[session.pk for session in sessions], member=membership
        )
        my_answers = {rsvp.session_id: rsvp.answer for rsvp in my_rsvps}

    rows = []
    next_seen = False
    for session in sessions:
        cancelled = session.cancelled
        local_start = core.to_club_local(club, session.starts_at)
        gm = session.game_master
        gm_name = (gm.user.display_name or gm.user.email) if gm else ""
        if cancelled:
            my_answer = None
            is_next = False
            when_text = None
        else:
            my_answer = my_answers.get(session.pk, "none")
            if not next_seen:
                next_seen = True
                is_next = True
                delta_days = max(0, (local_start.date() - today).days)
                when_text = _when_text(delta_days)
            else:
                is_next = False
                when_text = None
        rows.append(
            {
                "id": session.pk,
                "title": session.title,
                "local_start": local_start,
                "zone_label": zone.key,
                "gm_name": gm_name,
                "yes_count": session.yes_count,
                "my_answer": my_answer,
                "cancelled": cancelled,
                "can_rsvp": not cancelled and session.starts_at > now,
                "detail_url": reverse("play_sessions:session_detail", args=[club.slug, session.pk]),
                "is_next": is_next,
                "when_text": when_text,
            }
        )

    first_month = None
    if rows:
        first_local = rows[0]["local_start"]
        first_month = (first_local.year, first_local.month)

    return {"sessions": rows, "first_month": first_month}
