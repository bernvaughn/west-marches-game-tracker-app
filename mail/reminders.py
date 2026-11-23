"""Job function for sending session reminders (E5).

This module provides the send_reminders() function that runs periodically
to send reminders for upcoming play sessions.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership
from mail.builders_sessions import build_reminder
from mail.jobs import register_job
from mail.models import ClubMailSettings, EmailMessage, EmailPreference, NoticeSent
from mail.service import queue_email
from play_sessions.models import PlaySession, SessionRSVP
from player_characters.models import Character


def send_reminders() -> None:
    """Send reminders for sessions starting in the configured reminder windows.

    Runs every minute via run_mail_jobs. Deduplicates using NoticeSent.
    Only sends to members with characters who have not answered "no" and
    have not opted out via EmailPreference.
    """
    now = timezone.now()

    for club in ClubMailSettings.objects.all().select_related("club"):
        settings_obj = club
        club_obj = club.club
        reminder_days = settings_obj.reminder_days or [3]

        for days in reminder_days:
            _send_reminders_for_days(club_obj, days, now)


def _send_reminders_for_days(club, days: int, now) -> None:
    """Send reminders for a specific days-before value."""
    window_start = now + timedelta(days=days) - timedelta(minutes=1)
    window_end = now + timedelta(days=days) + timedelta(minutes=1)

    sessions = PlaySession.objects.filter(
        club=club,
        cancelled=False,
        starts_at__gte=window_start,
        starts_at__lt=window_end,
    ).select_related("game_master__user")

    for session in sessions:
        _send_session_reminder(club, session, days)


def _send_session_reminder(club, session: PlaySession, days: int) -> None:
    """Send reminder for a single session to all eligible members."""
    # Get all memberships with at least one character in this club
    memberships = (
        Membership.objects.filter(club=club)
        .exclude(characters__isnull=True)
        .distinct()
        .select_related("user")
    )

    for membership in memberships:
        # Skip if every character answered "no"
        if _all_characters_said_no(membership, session):
            continue

        # Skip if opted out of reminders
        if _is_opted_out(membership, EmailPreference.Kind.REMINDER):
            continue

        user = membership.user
        key = f"{session.id}:{days}"

        # Check dedupe
        if NoticeSent.objects.filter(kind=NoticeSent.Kind.REMINDER, key=key, user=user).exists():
            continue

        # Check if email is suppressed
        if _is_suppressed(user.email):
            continue

        # Build email
        subject, text, html = build_reminder(club, session, days)

        # Queue the email
        result = queue_email(
            kind=EmailMessage.Kind.REMINDER,
            to=user.email,
            club=club,
            subject=subject,
            text=text,
            html=html,
            user=user,
        )

        # On success, record NoticeSent
        if result.status == "queued" and result.message:
            with transaction.atomic():
                NoticeSent.objects.create(
                    kind=NoticeSent.Kind.REMINDER,
                    key=key,
                    user=user,
                )


def _all_characters_said_no(membership: Membership, session: PlaySession) -> bool:
    """Return True if all of this member's characters in the club have RSVP'd 'no'."""
    character_ids = Character.objects.filter(owner=membership).values_list("id", flat=True)
    if not character_ids:
        return True

    # Check if any character has NOT answered "no"
    no_count = SessionRSVP.objects.filter(
        session=session, character_id__in=character_ids, answer=SessionRSVP.Answer.NO
    ).count()

    total_chars = len(character_ids)
    return no_count == total_chars


def _is_opted_out(membership: Membership, kind: str) -> bool:
    """Check if the member has opted out of a given email kind."""
    pref = EmailPreference.objects.filter(membership=membership, kind=kind).first()
    return pref is not None and pref.enabled is False


def _is_suppressed(email: str) -> bool:
    """Check if an email is suppressed (do-not-email or .invalid)."""
    normalized = email.strip().lower()
    if normalized.endswith(".invalid"):
        return True
    from mail.models import DoNotEmail

    return DoNotEmail.objects.filter(address=normalized).exists()


# Register the job
register_job("send_reminders", send_reminders)
