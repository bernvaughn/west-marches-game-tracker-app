"""Hooks for the schedule feature: navigation entries and session sections."""

from django.urls import reverse

from accounts import navigation
from accounts.apps import is_gm_or_admin

from . import core
from .services import remaining_in_series


def _manage_context(request, session):
    """Build context for the Manage session section."""
    club = request.club
    if not core.can_manage_sessions(request.user, club):
        return {}

    ctx = {
        "edit_url": reverse("play_sessions:session_edit", args=[club.slug, session.pk]),
        "cancel_url": reverse("play_sessions:session_cancel", args=[club.slug, session.pk]),
    }
    if session.series_id:
        remaining = remaining_in_series(session)
        if remaining.exists():
            ctx["series_cancel_url"] = reverse(
                "play_sessions:series_cancel", args=[club.slug, session.pk]
            )
    return ctx


def _manage_visible(request, session):
    return core.can_manage_sessions(request.user, request.club)


def register():
    nav = navigation.register
    nav(
        "gm",
        "New session",
        "play_sessions:session_create",
        is_gm_or_admin,
        25,
    )

    core.register_session_section(
        "manage",
        order=90,
        template="play_sessions/_manage_section.html",
        context_fn=_manage_context,
        visible_fn=_manage_visible,
    )
