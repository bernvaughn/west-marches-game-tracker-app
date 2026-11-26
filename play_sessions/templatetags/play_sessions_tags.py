"""Template tags for the play_sessions app."""

from django import template
from django.utils import timezone

from ..calendar import next_session
from ..models import PlayerRSVP

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
    membership = getattr(request, "membership", None)
    return {"provider_context": _next_session_ctx(club, membership)}


def _next_session_ctx(club, membership=None):
    session = next_session(club, timezone.now())
    if session is not None and membership is not None:
        my_rsvp = PlayerRSVP.objects.filter(
            session_id=session["session_id"], member=membership
        ).first()
        if my_rsvp:
            session["my_answer"] = my_rsvp.answer
    return {"session": session, "club": club}
