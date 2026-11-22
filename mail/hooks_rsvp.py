"""Hooks for email RSVP (E6): register email extra for session_reminder."""

from mail.builders_rsvp import build_rsvp_extra


def register():
    """Register the RSVP email extra for session_reminder kind."""
    from mail.builders import register_email_extra

    register_email_extra("reminder", build_rsvp_extra)
