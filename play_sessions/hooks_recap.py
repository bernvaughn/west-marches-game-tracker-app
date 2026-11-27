"""Hooks for the recap feature: registers the session detail section and the
last-session dashboard provider.
"""

from django.urls import reverse
from django.utils import timezone

from accounts.dashboard_providers import BaseDashboardProvider, register_provider

from . import core, last_session


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


class LastSessionProvider(BaseDashboardProvider):
    """Dashboard provider for the 'Last session' card.

    Key: last_session
    Order: 10 (after quick_actions at 1, before notices at 2)
    """

    key = "last_session"
    order = 10
    template = "play_sessions/_dashboard_last_session.html"

    def get_context(self, request, club, character, membership):
        now = timezone.now()
        context = last_session.build(club, membership, character, now)
        if context is None:
            return {}
        return {"last_session": context}

    def should_show(self, request, club, character, membership):
        now = timezone.now()
        return last_session.latest_ended_session(club, now) is not None


def register():
    """Register the recap section for session detail and the last-session provider."""
    core.register_session_section(
        key="recap",
        order=80,
        template="play_sessions/_recap_section.html",
        context_fn=_context_fn,
        visible_fn=_visible_fn,
    )
    register_provider(LastSessionProvider())
