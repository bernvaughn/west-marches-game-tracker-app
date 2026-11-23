"""Password reset and password-changed notice hooks registration."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from mail.builders import render_email
from mail.service import queue_email


def register():
    """Register password-related hooks. Called from MailConfig.ready()."""
    # Receivers are registered via @receiver decorators below
    pass


@receiver(pre_save, sender="accounts.User")
def _user_pre_save_password_notice(sender, instance, **kwargs):
    """
    Flag when the password hash changes.

    Skips:
    - Account creation (pk is None)
    - When _mail_skip_password_notice is set on the instance
    """
    if instance.pk is None:
        # Account creation - skip
        return

    if getattr(instance, "_mail_skip_password_notice", False):
        # Explicitly skipped (e.g., welcome flow, password reset flow)
        return

    # Check if password hash changed
    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.password != instance.password:
        # Password hash changed - flag for post_save
        instance._mail_password_notice_pending = True


@receiver(post_save, sender="accounts.User")
def _user_post_save_password_notice(sender, instance, created, **kwargs):
    """
    Send password-changed notice after any password change except creation.

    The notice is queued with club=None (no reply-to for users in multiple clubs).
    """
    if created:
        # Account creation - no notice
        return

    if not getattr(instance, "_mail_password_notice_pending", False):
        # No password change detected
        return

    # Check if explicitly skipped
    if getattr(instance, "_mail_skip_password_notice", False):
        return

    # Send the notice
    subject, text, html = render_email(
        "password_changed",
        "password_changed",
        {
            "subject": "Your password was changed",
            "user": instance,
            "club": None,
        },
        None,
    )

    queue_email(
        kind="password_changed",
        to=instance.email,
        club=None,
        subject=subject,
        text=text,
        html=html,
        user=instance,
    )
