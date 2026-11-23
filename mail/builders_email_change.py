"""Builder for email change emails (E9).

Provides builder functions for:
- confirm_email: sent to the new address with confirmation link
- email_changed: sent to the old address after change is confirmed
"""

from mail.builders import render_email


def build_confirm_email(context: dict) -> tuple[str, str, str]:
    """Build the confirmation email sent to the new address.

    Context: user, club, new_email, confirm_url, site_url
    """
    subject = "Confirm your new email address"
    context["subject"] = subject
    return render_email("email_change", "confirm_email", context, context.get("club"))


def build_email_changed_notice(context: dict) -> tuple[str, str, str]:
    """Build the 'email changed' notice sent to the old address.

    Context: user, club, old_email, new_email, site_url
    """
    subject = "Your email address has been changed"
    context["subject"] = subject
    return render_email("email_change", "email_changed", context, context.get("club"))
