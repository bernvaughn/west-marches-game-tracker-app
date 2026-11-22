"""Hooks for RSVP (P4): session section, dashboard provider, sheet section."""

import logging

from django.utils import timezone

from accounts.dashboard_providers import BaseDashboardProvider, register_provider

from . import core
from .models import PlaySession
from .rsvp_forms import (
    answerable_characters,
    default_character,
    rsvp_answers,
)

logger = logging.getLogger(__name__)


# --- Session detail section --------------------------------------------------


def _rsvp_section_context(request, session):
    """Build context for the RSVP section template."""
    chars = answerable_characters(request)
    answers = rsvp_answers(session, chars)
    locked = session.starts_at <= timezone.now()
    cancelled = session.cancelled
    default = default_character(request)
    default_id = default.pk if default else None

    return {
        "session": session,
        "characters": chars,
        "answers": answers,
        "locked": locked,
        "cancelled": cancelled,
        "default_character_id": default_id,
        "can_manage": core.can_manage_sessions(request.user, session.club),
    }


def _rsvp_section_visible(request, session) -> bool:
    """Hide section only for a manager with no characters."""
    if core.can_manage_sessions(request.user, session.club):
        return len(answerable_characters(request)) > 0
    return True


# --- Dashboard provider ------------------------------------------------------


class MySessionsProvider(BaseDashboardProvider):
    """Dashboard provider: My sessions (my RSVP answers for the selected character)."""

    key = "my_sessions"
    order = 9
    template = "play_sessions/_dashboard_rsvps.html"

    def get_context(self, request, club, character, membership):
        """Return upcoming sessions with the selected character's RSVP answer."""
        # Only show for active characters
        if not core.character_is_active(character):
            return {"sessions": []}

        now = timezone.now()
        sessions = (
            PlaySession.objects.for_club(club)
            .filter(starts_at__gt=now, cancelled=False)
            .order_by("starts_at")[:5]
        )

        session_data = []
        for session in sessions:
            # Get RSVP for this character
            from .models import SessionRSVP

            rsvp = SessionRSVP.objects.filter(session=session, character=character).first()
            answer = rsvp.answer if rsvp else None

            # Convert to club local time
            starts_local = core.to_club_local(club, session.starts_at)
            session_data.append(
                {
                    "session": session,
                    "starts_local": starts_local,
                    "answer": answer,
                    "can_answer": True,  # Owner can always answer (if not locked)
                }
            )

        return {"sessions": session_data}

    def should_show(self, request, club, character, membership) -> bool:
        return core.character_is_active(character)


# --- Character sheet section -------------------------------------------------


def _sheet_rsvps_context(request, character):
    """Return context for the sheet RSVP section."""
    if not core.character_is_active(character):
        return None

    club = getattr(request, "club", None)
    if club is None:
        return None

    now = timezone.now()
    sessions = (
        PlaySession.objects.for_club(club)
        .filter(starts_at__gt=now, cancelled=False)
        .order_by("starts_at")
    )

    # Get RSVPs for this character
    from .models import SessionRSVP

    rsvp_map = {
        r.session_id: r.answer
        for r in SessionRSVP.objects.filter(
            session__in=sessions, character=character
        ).select_related("session")
    }

    session_data = []
    for session in sessions:
        answer = rsvp_map.get(session.pk)
        starts_local = core.to_club_local(club, session.starts_at)

        # Determine if the viewer may answer (owner, GM, admin)
        viewer_may_answer = False
        membership = getattr(request, "membership", None)
        if membership and character.owner_id == membership.id:
            viewer_may_answer = True
        elif core.can_manage_sessions(request.user, club):
            viewer_may_answer = True

        # Player can only answer before start
        player_can_answer = viewer_may_answer and session.starts_at > now

        session_data.append(
            {
                "session": session,
                "starts_local": starts_local,
                "answer": answer,
                "player_can_answer": player_can_answer,
                "is_manager": core.can_manage_sessions(request.user, club),
            }
        )

    return {"sessions": session_data}


def _sheet_rsvps_visible(request, character) -> bool:
    """Hide section for inactive characters."""
    return core.character_is_active(character)


def register():
    """Register RSVP hooks: session section, dashboard provider, sheet section."""
    # Session detail section
    core.register_session_section(
        key="rsvp",
        order=20,
        template="play_sessions/_rsvp_section.html",
        context_fn=_rsvp_section_context,
        visible_fn=_rsvp_section_visible,
    )

    # Dashboard provider
    register_provider(MySessionsProvider())

    # Character sheet section
    from player_characters.sheet_sections import register_sheet_section

    register_sheet_section(
        key="rsvps",
        order=10,
        template="play_sessions/_sheet_rsvps.html",
        context_fn=_sheet_rsvps_context,
        visible_fn=_sheet_rsvps_visible,
    )
