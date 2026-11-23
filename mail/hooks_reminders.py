"""Hooks for session reminders and cancel/change notices (E5).

Registers the admin nav entry, signal receivers, and ensures the job is registered.
"""

from django.db.models.signals import post_save, pre_save

from accounts.navigation import register as nav_register


def _is_admin_check(request):
    """Check if user is club admin."""
    from accounts.permissions import is_club_admin

    if not request.user.is_authenticated:
        return False
    club = getattr(request, "club", None)
    if club is None:
        return False
    return is_club_admin(request.user, club)


def register():
    """Register nav entry, signals, and ensure job is imported."""
    # Nav entry in admin group
    nav_register(
        "admin",
        "Reminders",
        "mail:reminder_settings",
        _is_admin_check,
        order=55,
    )

    # Ensure the job is registered
    import mail.reminders  # noqa: F401

    # Connect signals
    pre_save.connect(
        _capture_old_session_state,
        sender="play_sessions.PlaySession",
        dispatch_uid="mail_capture_old_session",
    )
    post_save.connect(
        _send_session_notices,
        sender="play_sessions.PlaySession",
        dispatch_uid="mail_send_session_notices",
    )


def _capture_old_session_state(sender, instance, **kwargs):
    """Capture old cancelled and starts_at values before save."""
    if instance.pk is None:
        # New instance, nothing to capture
        instance._mail_old_cancelled = False
        instance._mail_old_starts_at = None
        return

    try:
        old = sender.objects.get(pk=instance.pk)
        instance._mail_old_cancelled = old.cancelled
        instance._mail_old_starts_at = old.starts_at
    except sender.DoesNotExist:
        instance._mail_old_cancelled = False
        instance._mail_old_starts_at = None


def _send_session_notices(sender, instance, created, **kwargs):
    """Send cancel/change notices after session save."""
    if created:
        return  # No notices on creation

    old_cancelled = getattr(instance, "_mail_old_cancelled", False)
    old_starts_at = getattr(instance, "_mail_old_starts_at", None)

    # Cancelled: False -> True
    if not old_cancelled and instance.cancelled:
        _send_cancel_notices(instance)

    # Changed start time (not cancelled)
    elif (
        not instance.cancelled and old_starts_at is not None and instance.starts_at != old_starts_at
    ):
        _send_change_notices(instance, old_starts_at, instance.starts_at)

    # No notice on un-cancel or non-time changes


def _send_cancel_notices(session):
    """Send session_cancelled notices to reminder recipients + yes RSVPs."""
    from mail.builders_sessions import build_cancelled
    from mail.models import EmailMessage, NoticeSent
    from mail.service import queue_email
    from play_sessions.models import SessionRSVP

    club = session.club
    key_prefix = f"{session.id}:"

    # Get users who were sent a reminder for this session
    reminder_users = NoticeSent.objects.filter(
        kind=NoticeSent.Kind.REMINDER, key__startswith=key_prefix
    ).values_list("user_id", flat=True)

    # Get users with a "yes" RSVP
    yes_rsvp_user_ids = (
        SessionRSVP.objects.filter(session=session, answer=SessionRSVP.Answer.YES)
        .select_related("character__owner__user")
        .values_list("character__owner__user_id", flat=True)
    )

    # Combine and deduplicate
    target_user_ids = set(reminder_users) | set(yes_rsvp_user_ids)

    subject, text, html = build_cancelled(club, session)

    for user_id in target_user_ids:
        # Check dedupe for cancel
        cancel_key = f"{session.id}"
        if NoticeSent.objects.filter(
            kind=NoticeSent.Kind.CANCEL, key=cancel_key, user_id=user_id
        ).exists():
            continue

        # Get user for email
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            continue

        # Check if email is suppressed
        if _is_suppressed(user.email):
            continue

        result = queue_email(
            kind=EmailMessage.Kind.CANCEL,
            to=user.email,
            club=club,
            subject=subject,
            text=text,
            html=html,
            user=user,
        )

        if result.status == "queued" and result.message:
            NoticeSent.objects.create(
                kind=NoticeSent.Kind.CANCEL,
                key=cancel_key,
                user=user,
            )


def _send_change_notices(session, old_start, new_start):
    """Send session_changed notices to reminder-eligible members."""
    from accounts.models import Membership
    from mail.builders_sessions import build_changed
    from mail.models import EmailMessage, EmailPreference, NoticeSent
    from mail.reminders import _all_characters_said_no, _is_opted_out, _is_suppressed
    from mail.service import queue_email

    club = session.club

    # Get memberships with characters (same eligibility as reminders)
    memberships = (
        Membership.objects.filter(club=club)
        .exclude(characters__isnull=True)
        .distinct()
        .select_related("user")
    )

    subject, text, html = build_changed(club, session, old_start, new_start)

    for membership in memberships:
        # Skip if all characters said no
        if _all_characters_said_no(membership, session):
            continue

        # Skip if opted out of notices
        if _is_opted_out(membership, EmailPreference.Kind.NOTICE):
            continue

        user = membership.user
        # Dedupe key includes new start time
        change_key = f"{session.id}:{new_start.isoformat()}"

        if NoticeSent.objects.filter(
            kind=NoticeSent.Kind.CHANGE, key=change_key, user=user
        ).exists():
            continue

        if _is_suppressed(user.email):
            continue

        result = queue_email(
            kind=EmailMessage.Kind.CHANGE,
            to=user.email,
            club=club,
            subject=subject,
            text=text,
            html=html,
            user=user,
        )

        if result.status == "queued" and result.message:
            NoticeSent.objects.create(
                kind=NoticeSent.Kind.CHANGE,
                key=change_key,
                user=user,
            )


def _is_suppressed(email: str) -> bool:
    """Check if an email is suppressed (do-not-email or .invalid)."""
    normalized = email.strip().lower()
    if normalized.endswith(".invalid"):
        return True
    from mail.models import DoNotEmail

    return DoNotEmail.objects.filter(address=normalized).exists()
