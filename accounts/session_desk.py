"""Session desk data builder for GM and club admin club home."""

from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from accounts import approvals
from accounts.permissions import is_club_admin, is_game_master
from player_characters.selection import own_characters


def _is_gm_or_admin(request):
    return is_game_master(request.user, request.club) or is_club_admin(request.user, request.club)


def build_session_desk(request):
    """Build session desk data for the club home.

    Returns None if the user is not a GM or club admin.
    Otherwise returns a dict with:
    - "waiting": list of Approval items (same as pending_approvals)
    - "after": list of (label, url) tuples for post-session actions
    - "dashboard_url": str or None (player dashboard URL if user owns a character)
    - "coming_up": up to 3 upcoming session dicts
    - "club": Club
    - "membership": Membership
    - "can_manage_sessions": bool
    - "wrapup_session": PlaySession or None (the session the wrap-up panel covers)
    """
    if not _is_gm_or_admin(request):
        return None

    club = request.club
    membership = request.membership
    waiting = approvals.pending_approvals(request)

    # Find the wrap-up session to prefill the Award Loot link
    from play_sessions.hooks_wrapup import wrapup_session

    wrapup = wrapup_session(club, timezone.now())
    bulk_award_url = reverse("characters:bulk_award", args=[club.slug])
    if wrapup:
        bulk_award_url = f"{bulk_award_url}?session={wrapup.pk}"

    after = [
        ("Award Loot to Party", bulk_award_url),
        ("Downtime points", reverse("downtime:points_award", args=[club.slug])),
        ("Map", reverse("map:index", args=[club.slug])),
        ("Character slips", reverse("characters:slips", args=[club.slug])),
    ]

    dashboard_url = None
    if own_characters(request).exists():
        dashboard_url = reverse("accounts:player_dashboard", args=[club.slug])

    from play_sessions.core import can_manage_sessions
    from play_sessions.upcoming import upcoming_sessions

    coming_up = upcoming_sessions(club, timezone.now(), membership, 3)["sessions"]

    return {
        "waiting": waiting,
        "after": after,
        "dashboard_url": dashboard_url,
        "coming_up": coming_up,
        "club": club,
        "membership": membership,
        "can_manage_sessions": can_manage_sessions(request.user, club),
        "wrapup_session": wrapup,
    }
