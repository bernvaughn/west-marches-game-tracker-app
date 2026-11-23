"""Welcome email builders and extras registration."""

from mail.builders import register_email_extra


def welcome_extra(context):
    """Extra content for welcome emails - none needed for base welcome."""
    return "", ""


def added_to_club_extra(context):
    """Extra content for added_to_club emails - none needed."""
    return "", ""


def password_set_extra(context):
    """Extra content for password set page - none needed."""
    return "", ""


# Register extras (no-op for now, but allows future extension)
register_email_extra("welcome", welcome_extra)
register_email_extra("added_to_club", added_to_club_extra)
register_email_extra("welcome_set_password", password_set_extra)