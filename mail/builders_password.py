"""Password reset and password-changed notice email builders."""

from mail.builders import register_email_extra, render_email


def build_reset_password_email(context: dict) -> tuple[str, str, str]:
    """Build the password reset email (has reset link, 1-hour expiry)."""
    return render_email("password_reset", "password_reset", context, context.get("club"))


def build_password_changed_notice(context: dict) -> tuple[str, str, str]:
    """Build the password-changed notice email (no link)."""
    return render_email("password_changed", "password_changed", context, context.get("club"))


# Register no-op extras for future extension (pattern from builders_welcome.py)
def password_reset_extra(context):
    """Extra content for password_reset emails - none needed."""
    return "", ""


def password_changed_extra(context):
    """Extra content for password_changed emails - none needed."""
    return "", ""


register_email_extra("password_reset", password_reset_extra)
register_email_extra("password_changed", password_changed_extra)
