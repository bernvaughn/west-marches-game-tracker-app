"""Template tags for the play_sessions app."""

from django import template
from django.utils import timezone

from ..calendar import next_session

register = template.Library()


@register.inclusion_tag("play_sessions/_next_session.html", takes_context=True)
def next_session_block(context):
    """Render the Next session block for club home (GM / admin).

    Fetches its own data from ``request.club`` because club_home.html is
    rendered by accounts, which this app does not own.
    """
    request = context["request"]
    club = getattr(request, "club", None)
    if club is None:
        return {"provider_context": {"session": None}}
    return {"provider_context": _next_session_ctx(club)}


def _next_session_ctx(club):
    session = next_session(club, timezone.now())
    return {"session": session, "club": club}
