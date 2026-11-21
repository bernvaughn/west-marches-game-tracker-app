"""Hooks for attendance feature (P5, P6).

Registers the "Who is coming" section and provides the manager-only
"Take attendance" button inside that section.
"""

from django.urls import reverse

from . import core
from .services_attendance import who_is_coming


def _who_is_coming_context(request, session):
    """Context function for the "Who is coming" section."""
    data = who_is_coming(session)
    club = request.club
    can_manage = core.can_manage_sessions(request.user, club)
    return {
        "groups": data["groups"],
        "unanswered": data["unanswered"],
        "can_manage": can_manage,
        "attendance_url": reverse(
            "play_sessions:attendance",
            kwargs={"club_slug": club.slug, "pk": session.pk},
        ),
        "rsvp_for_url": reverse(
            "play_sessions:rsvp_for",
            kwargs={"club_slug": club.slug, "pk": session.pk},
        ),
        "rsvp_form": None,  # Filled in by the section template
        "attendance_recorded": session.attendance.count(),
    }


def register():
    """Register the "Who is coming" session section."""
    # Import lazily to avoid circular imports during app loading
    from .attendance_forms import RsvpForClubForm

    def context_fn(request, session):
        ctx = _who_is_coming_context(request, session)
        ctx["rsvp_form"] = RsvpForClubForm(request.club)
        return ctx

    # Visible to all club members (checked in session_detail via club_member_required)
    core.register_session_section(
        "who_is_coming",
        20,
        "play_sessions/_who_is_coming.html",
        context_fn,
        visible_fn=lambda request, session: True,
    )
