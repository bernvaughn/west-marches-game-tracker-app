"""Hooks for wrap-up feature (P21).

Provides a helper to find the latest ended session and registers the
"Wrap up" session section for managers.
"""

from django.db.models import F
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from . import core
from .models import PlaySession


def wrapup_session(club, now):
    """Return the most recent non-cancelled session that has ended, within 14 days.

    Effective end = Coalesce(ends_at, starts_at). A session with no end time
    counts as ended once it starts.

    Args:
        club: The club to search in.
        now: The reference time (typically timezone.now()).

    Returns:
        PlaySession or None.
    """
    cutoff = now - timezone.timedelta(days=14)
    return (
        PlaySession.objects.for_club(club)
        .filter(cancelled=False)
        .annotate(effective_end=Coalesce("ends_at", "starts_at"))
        .filter(effective_end__lte=now, effective_end__gte=cutoff)
        .order_by("-effective_end", "-id")
        .first()
    )


def _context_fn(request, session):
    club = request.club
    attendance_done = session.attendance.exists()
    recap_done = bool(session.recap.strip())

    attendance_url = reverse(
        "play_sessions:attendance", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    recap_edit_url = reverse(
        "play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk}
    )
    bulk_award_url = reverse("characters:bulk_award", args=[club.slug])
    downtime_url = reverse("downtime:points_award", args=[club.slug])

    return {
        "attendance_done": attendance_done,
        "recap_done": recap_done,
        "attendance_url": attendance_url,
        "recap_edit_url": recap_edit_url,
        "bulk_award_url": f"{bulk_award_url}?session={session.pk}",
        "downtime_url": downtime_url,
    }


def _visible_fn(request, session):
    """Show only for managers, only on the wrap-up session itself."""
    if not core.can_manage_sessions(request.user, request.club):
        return False
    ws = wrapup_session(request.club, timezone.now())
    return ws is not None and ws.pk == session.pk


def register():
    """Register the "Wrap up" session section."""
    core.register_session_section(
        key="wrapup",
        order=10,
        template="play_sessions/_wrapup_section.html",
        context_fn=_context_fn,
        visible_fn=_visible_fn,
    )