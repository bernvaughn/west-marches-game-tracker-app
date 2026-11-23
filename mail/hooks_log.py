"""Club-scoped mail hooks for log and pruning."""

from accounts.apps import is_admin
from accounts.navigation import register as nav_register
from mail.jobs import register_job


def _prune_job():
    """Job function to prune old email messages."""
    from django.core.management import call_command

    call_command("prune_email")


def register():
    # Nav entry: "Email log" in admin group
    nav_register(
        "admin",
        "Email log",
        "mail:log",
        is_admin,
        50,
    )
    # Register prune job
    register_job("prune_email", _prune_job)
