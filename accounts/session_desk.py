"""Session desk data builder for GM and club admin club home."""

from __future__ import annotations

from django.urls import reverse

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
    """
    if not _is_gm_or_admin(request):
        return None

    club = request.club
    waiting = approvals.pending_approvals(request)

    after = [
        ("Award Loot to Party", reverse("characters:bulk_award", args=[club.slug])),
        ("Downtime points", reverse("downtime:points_award", args=[club.slug])),
        ("Map", reverse("map:index", args=[club.slug])),
        ("Character slips", reverse("characters:slips", args=[club.slug])),
    ]

    dashboard_url = None
    if own_characters(request).exists():
        dashboard_url = reverse("accounts:player_dashboard", args=[club.slug])

    return {
        "waiting": waiting,
        "after": after,
        "dashboard_url": dashboard_url,
    }
