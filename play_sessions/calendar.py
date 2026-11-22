"""Pure helpers for the session month grid, upcoming list and next session."""

import calendar as cal_module
from datetime import date, datetime, time

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from . import core
from .models import PlaySession

_MIN_YEAR = 2000
_MAX_YEAR = 2100


def parse_month(value, today):
    """Read ``?month=YYYY-MM``. Bad or out-of-range input falls back to the current month.

    Returns a ``(year, month)`` tuple.
    """
    today = today or timezone.localdate()
    try:
        year, month = (int(part) for part in str(value).split("-"))
    except (AttributeError, ValueError, TypeError):
        return today.year, today.month
    if not (_MIN_YEAR <= year <= _MAX_YEAR and 1 <= month <= 12):
        return today.year, today.month
    return year, month


def month_grid(club, year, month, today):
    """Build the month grid: weeks of 7 days, Sunday first.

    Each day holds ``date``, ``in_month``, ``is_today`` and ``sessions``.
    One query covers the grid's UTC range. Sessions group by their
    club-local start date. Returns ``{"weeks", "prev_month", "next_month"}``.
    """
    today = today or timezone.localdate()
    month_cal = cal_module.Calendar(firstweekday=6)  # Sunday first
    all_dates = []
    weeks = []
    for week in month_cal.monthdatescalendar(year, month):
        week_days = []
        for d in week:
            all_dates.append(d)
            week_days.append(
                {
                    "date": d,
                    "in_month": d.month == month,
                    "is_today": d == today,
                    "sessions": [],
                }
            )
        weeks.append(week_days)

    start_utc = core.from_club_local(club, datetime.combine(all_dates[0], time.min))
    end_utc = core.from_club_local(club, datetime.combine(all_dates[-1], time.max))
    sessions = (
        PlaySession.objects.for_club(club)
        .filter(starts_at__gte=start_utc, starts_at__lte=end_utc)
        .select_related("game_master__user")
        .annotate(yes_count=Count("rsvps", filter=Q(rsvps__answer="yes")))
        .order_by("starts_at")
    )
    by_date = {}
    for session in sessions:
        local_start = core.to_club_local(club, session.starts_at)
        session.local_start = local_start
        by_date.setdefault(local_start.date(), []).append(session)
    for week in weeks:
        for day in week:
            day["sessions"] = by_date.get(day["date"], [])

    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
    return {
        "weeks": weeks,
        "prev_month": f"{prev_year}-{prev_month:02d}",
        "next_month": f"{next_year}-{next_month:02d}",
    }


def upcoming_list(club, year, month, today):
    """Sessions of the shown month, grouped by day.

    The current month hides days before today. Other months show everything.
    Returns a list of ``{"date", "sessions"}``.
    """
    today = today or timezone.localdate()
    first = date(year, month, 1)
    last_day = cal_module.monthrange(year, month)[1]
    last = date(year, month, last_day)
    start_utc = core.from_club_local(club, datetime.combine(first, time.min))
    end_utc = core.from_club_local(club, datetime.combine(last, time.max))
    qs = (
        PlaySession.objects.for_club(club)
        .filter(starts_at__gte=start_utc, starts_at__lte=end_utc)
        .select_related("game_master__user")
        .annotate(yes_count=Count("rsvps", filter=Q(rsvps__answer="yes")))
        .order_by("starts_at")
    )
    if (year, month) == (today.year, today.month):
        today_start_utc = core.from_club_local(club, datetime.combine(today, time.min))
        qs = qs.filter(starts_at__gte=today_start_utc)
    by_date = {}
    for session in qs:
        local_start = core.to_club_local(club, session.starts_at)
        session.local_start = local_start
        by_date.setdefault(local_start.date(), []).append(session)
    return [{"date": d, "sessions": by_date[d]} for d in sorted(by_date)]


def next_session(club, now):
    """First non-cancelled session starting or ending at/after ``now``.

    Returns a context dict (title, local_start, gm_name, yes_count, detail_url)
    or None when there is no upcoming session.
    """
    qs = (
        PlaySession.objects.for_club(club)
        .filter(cancelled=False)
        .filter(Q(starts_at__gte=now) | Q(ends_at__gte=now))
        .select_related("game_master__user")
        .annotate(yes_count=Count("rsvps", filter=Q(rsvps__answer="yes")))
        .order_by("starts_at")
    )
    session = qs.first()
    if session is None:
        return None
    local_start = core.to_club_local(club, session.starts_at)
    gm = session.game_master
    gm_name = (gm.user.display_name or gm.user.email) if gm else ""
    return {
        "title": session.title,
        "local_start": local_start,
        "zone_name": core.club_zone(club).key,
        "gm_name": gm_name,
        "yes_count": session.yes_count,
        "detail_url": reverse("play_sessions:session_detail", args=[club.slug, session.pk]),
    }
