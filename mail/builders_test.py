"""Test email builder."""

from mail.builders import render_email


def build_test_email(club, sender) -> tuple[str, str, str]:
    """Build a test email for the club.

    Returns (subject, text, html).
    """
    context = {
        "subject": f"[Test] {club.name} - Test email",
        "club_name": club.name,
        "sender_name": getattr(sender, "display_name", None) or sender.email,
        "sender_email": sender.email,
    }
    return render_email("test", "test", context, club)