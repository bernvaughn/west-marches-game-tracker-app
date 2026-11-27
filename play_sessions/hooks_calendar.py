"""Hooks for the calendar feature: nav entry and the Next session dashboard provider.

Registered automatically from ``PlaySessionsConfig.ready()`` via
``core.load_hooks()``. The accounts imports live inside ``register()`` to avoid
circular imports at app load time.
"""

from django.urls import reverse
from django.utils import timezone

from .core import can_manage_sessions
from .upcoming import upcoming_sessions


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
        """'Upcoming sessions' list for the player dashboard."""

        key = "next_session"
        order = 2
        template = "play_sessions/_next_session.html"

        def get_context(self, request, club, character, membership):
            return _next_session_ctx(request, club, membership)

        def should_show(self, request, club, character, membership):
            # Always show so the HTMX partial endpoint never 404s.
            return True

    register_provider(NextSessionDashboardProvider())


def _next_session_ctx(request, club, membership=None):
    """Wrap ``upcoming_sessions`` for the dashboard provider.

    Returns ``{"coming_up", "club", "membership", "can_manage_sessions",
    "show_rsvp", "rsvp_next"}``. The club-home inclusion tag builds its own
    context without these keys, so club home keeps badge and link only.
    """
    now = timezone.now()
    data = upcoming_sessions(club, now, membership, limit=3)
    return {
        "coming_up": data["sessions"],
        "club": club,
        "membership": membership,
        "can_manage_sessions": can_manage_sessions(request.user, club),
        "show_rsvp": True,
        "rsvp_next": reverse("accounts:player_dashboard", args=[club.slug]),
    }
