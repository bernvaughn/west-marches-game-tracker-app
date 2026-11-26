"""Hooks for RSVP (P13): session section, dashboard provider."""

import logging

from django.utils import timezone

from accounts.dashboard_providers import BaseDashboardProvider, register_provider

from . import core
from .models import PlayerRSVP, PlaySession
from .rsvp_forms import rsvp_answers

logger = logging.getLogger(__name__)


# --- Session detail section --------------------------------------------------


def _rsvp_section_context(request, session):
    """Build context for the RSVP section template."""
    membership = getattr(request, "membership", None)
    if membership is None:
        return {
            "session": session,
            "my_answer": None,
            "locked": True,
            "cancelled": session.cancelled,
            "can_manage": False,
            "all_answers": {},
            "members": [],
        }

    # Get player's answer
    my_rsvp = PlayerRSVP.objects.filter(session=session, member=membership).first()
    my_answer = my_rsvp.answer if my_rsvp else None

    locked = session.starts_at <= timezone.now()
    cancelled = session.cancelled
    can_manage = core.can_manage_sessions(request.user, session.club)

    # For managers: get all members' answers grouped by answer
    all_answers = {}
    members = []
    if can_manage:
        from accounts.models import Membership

        members = list(
            Membership.objects.for_club(session.club)
            .select_related("user")
            .order_by("user__display_name", "user__email")
        )
        answers_map = rsvp_answers(session, members)
        for member in members:
            answer = answers_map.get(member.id)
            all_answers.setdefault(answer, []).append(member)

    # Define answer groups for manager view (ordered: yes, maybe, no, None)
    answer_groups = [
        ("Yes", "yes"),
        ("Maybe", "maybe"),
        ("No", "no"),
        ("Not answered", None),
    ]

    return {
        "session": session,
        "my_answer": my_answer,
        "locked": locked,
        "cancelled": cancelled,
        "can_manage": can_manage,
        "all_answers": all_answers,
        "members": members,
        "answer_groups": answer_groups,
    }


def _rsvp_section_visible(request, session) -> bool:
    """Show for all members (managers always, players if they have membership)."""
    return True


# --- Dashboard provider ------------------------------------------------------


class MySessionsProvider(BaseDashboardProvider):
    """Dashboard provider: My sessions (my RSVP answers for my membership)."""

    key = "my_sessions"
    order = 9
    template = "play_sessions/_dashboard_rsvps.html"

    def get_context(self, request, club, character, membership):
        """Return upcoming sessions with the membership's RSVP answer."""
        if membership is None:
            return {"sessions": []}

        now = timezone.now()
        sessions = (
            PlaySession.objects.for_club(club)
            .filter(starts_at__gt=now, cancelled=False)
            .order_by("starts_at")[:5]
        )

        session_data = []
        for session in sessions:
            # Get RSVP for this membership
            rsvp = PlayerRSVP.objects.filter(session=session, member=membership).first()
            answer = rsvp.answer if rsvp else None

            # Convert to club local time
            starts_local = core.to_club_local(club, session.starts_at)
            # Player can answer if not locked and not cancelled
            can_answer = session.starts_at > now

            session_data.append(
                {
                    "session": session,
                    "starts_local": starts_local,
                    "answer": answer,
                    "can_answer": can_answer,
                }
            )

        return {"sessions": session_data}

    def should_show(self, request, club, character, membership) -> bool:
        return membership is not None


def register():
    """Register RSVP hooks: session section and dashboard provider."""
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
