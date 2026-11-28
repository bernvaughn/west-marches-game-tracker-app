"""Demo data for mail. Safe to run more than once."""

from mail.models import ClubMailSettings


def seed(club):
    """Seed demo club mail settings.

    Sets the contact email so the "message the admins" feature has a
    reply-to address. Idempotent via get_or_create.
    """
    ClubMailSettings.objects.get_or_create(
        club=club,
        defaults={"contact_email": "gm@example.com"},
    )
