"""Hooks for the calendar feature: nav entry and the Next session dashboard provider.

Registered automatically from ``PlaySessionsConfig.ready()`` via
``core.load_hooks()``. The accounts imports live inside ``register()`` to avoid
circular imports at app load time.
"""

from django.utils import timezone

from .calendar import next_session


def register():
    from accounts import navigation
    from accounts.apps import is_member
    from accounts.dashboard_providers import BaseDashboardProvider, register_provider

    reg = navigation.register
    reg(
        "club",
        "Sessions",
        "play_sessions:calendar",
        is_member,
        55,
        icon="calendar-date",
        shortcut_order=55,
    )

    class NextSessionDashboardProvider(BaseDashboardProvider):
        """'Next session' card for the player dashboard."""

        key = "next_session"
        order = 2
        template = "play_sessions/_next_session.html"

        def get_context(self, request, club, character, membership):
            return _next_session_ctx(club)

        def should_show(self, request, club, character, membership):
            # Always show so the HTMX partial endpoint never 404s.
            return True

    register_provider(NextSessionDashboardProvider())


def _next_session_ctx(club):
    """Wrap ``next_session`` so the empty state is ``{"session": None}``."""
    session = next_session(club, timezone.now())
    return {"session": session, "club": club}
