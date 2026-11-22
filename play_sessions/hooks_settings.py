"""Hooks for session settings feature."""

from accounts import navigation
from accounts.apps import is_admin as is_admin_check
from play_sessions import core


def register():
    """Register nav entry and signal receiver for session settings."""
    # Nav entry in admin group, order 60 (after Inbox at 30)
    navigation.register(
        "admin",
        "Session settings",
        "play_sessions:settings",
        is_admin_check,
        60,
    )

    # Connect attendance_saved signal receiver
    from .awards import apply_attendance_awards

    core.attendance_saved.connect(
        apply_attendance_awards, dispatch_uid="play_sessions.award_points"
    )
