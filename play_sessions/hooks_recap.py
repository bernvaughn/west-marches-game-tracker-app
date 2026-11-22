"""Hooks for the recap feature: registers the session detail section."""

from django.urls import reverse

from . import core


def _context_fn(request, session):
    club = request.club
    manager = core.can_manage_sessions(request.user, club)
    context = {
        "recap": session.recap,
        "can_edit_recap": manager,
        "recap_edit_url": reverse(
            "play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk}
        ),
    }
    if manager:
        context["gm_notes"] = session.gm_notes
    return context


def _visible_fn(request, session):
    manager = core.can_manage_sessions(request.user, request.club)
    if manager:
        return True
    return bool(session.recap.strip())


def register():
    """Register the recap section for session detail."""
    core.register_session_section(
        key="recap",
        order=80,
        template="play_sessions/_recap_section.html",
        context_fn=_context_fn,
        visible_fn=_visible_fn,
    )