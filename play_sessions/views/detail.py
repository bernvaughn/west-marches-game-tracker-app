from django.shortcuts import render
from django.template.loader import render_to_string

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from .. import core
from ..models import PlaySession


@club_member_required
def session_detail(request, club_slug, pk):
    """Render the session detail page with plug-in sections.

    The view is scoped to the current club via club_get_object_or_404,
    which returns 404 if the session belongs to another club.
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)

    club = request.club
    can_manage = core.can_manage_sessions(request.user, club)
    zone = core.club_zone(club)

    # Convert times to club local for display
    starts_local = core.to_club_local(club, session.starts_at)
    ends_local = core.to_club_local(club, session.ends_at) if session.ends_at else None

    # Render registered sections
    sections_html = []
    for section in core.session_sections(request, session):
        context = {
            "request": request,
            "session": session,
            "club": club,
            "can_manage": can_manage,
            **section["context_fn"](request, session),
        }
        html = render_to_string(section["template"], context, request=request)
        sections_html.append({"key": section["key"], "html": html})

    context = {
        "session": session,
        "club": club,
        "can_manage": can_manage,
        "starts_local": starts_local,
        "ends_local": ends_local,
        "zone_name": zone.key,
        "sections": sections_html,
    }
    return render(request, "play_sessions/session_detail.html", context)
