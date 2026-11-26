"""Template tags for the play_sessions app."""

from django import template
from django.utils import timezone

from ..core import can_manage_sessions
from ..timefmt import format_session_time
from ..upcoming import upcoming_sessions

register = template.Library()


@register.filter
def session_time(moment, club):
    """Template filter: format a datetime with the club's zone short name.

    Usage: {{ moment|session_time:club }}
    Returns string like "7:00 PM EDT" or "7:00 PM EST".
    """
    return format_session_time(moment, club)


@register.inclusion_tag("play_sessions/_next_session.html", takes_context=True)
def next_session_block(context):
    """Render the upcoming-sessions block for club home (GM / admin).

    Fetches its own data from ``request.club`` because club_home.html is
    rendered by accounts, which this app does not own.
    """
    request = context["request"]
    club = getattr(request, "club", None)
    if club is None:
        return {
            "provider_context": {
                "coming_up": [],
                "club": None,
                "membership": None,
                "can_manage_sessions": False,
            }
        }
    membership = getattr(request, "membership", None)
    return {"provider_context": _next_session_ctx(club, membership, request.user)}


def _next_session_ctx(club, membership, user):
    data = upcoming_sessions(club, timezone.now(), membership, 3)
    return {
        "coming_up": data["sessions"],
        "club": club,
        "membership": membership,
        "can_manage_sessions": can_manage_sessions(user, club),
    }
