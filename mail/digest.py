"""Job function for sending Game Master digests (E7).

This module provides the send_digests() function that runs periodically
to send digests to game masters about upcoming sessions.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from mail.builders_digest import build_digest
from mail.jobs import register_job
from mail.models import EmailMessage, EmailPreference, NoticeSent
from mail.service import queue_email
from play_sessions.models import PlaySession, SessionRSVP
from player_characters.models import Character


def send_digests() -> None:
    """Send digests for sessions starting in ~24 hours.

    Runs every minute via run_mail_jobs. Deduplicates using NoticeSent.
    Only sends to game masters who have EmailPreference(kind="digest", enabled=True).
    """
    now = timezone.now()
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)

    # Find sessions starting in the 24-hour window
    sessions = PlaySession.objects.filter(
        starts_at__gte=window_start,
        starts_at__lt=window_end,
        cancelled=False,
        game_master__isnull=False,
    ).select_related("club", "game_master__user")

    for session in sessions:
        _process_session(session, now)


def _process_session(session: PlaySession, now) -> None:
    """Process a single session for digest sending."""
    gm_membership = session.game_master
    gm_user = gm_membership.user

    # Check if GM has digest preference enabled
    if not EmailPreference.objects.filter(
        membership=gm_membership, kind=EmailPreference.Kind.DIGEST, enabled=True
    ).exists():
        return

    # Check dedupe: has this digest already been sent for this session?
    key = f"{session.id}:{session.starts_at.isoformat()}"
    if NoticeSent.objects.filter(kind=NoticeSent.Kind.DIGEST, key=key, user=gm_user).exists():
        return

    # Check if GM email is deliverable
    if _is_suppressed(gm_user.email):
        return

    # Build RSVP groups
    rsvp_groups = _build_rsvp_groups(session)

    # Build email content
    subject, text, html = build_digest(session.club, session, gm_membership, rsvp_groups)

    # Queue the email
    result = queue_email(
        kind=EmailMessage.Kind.DIGEST,
        to=gm_user.email,
        club=session.club,
        subject=subject,
        text=text,
        html=html,
        user=gm_user,
    )

    # On success, record NoticeSent
    if result.status == "queued" and result.message:
        with transaction.atomic():
            NoticeSent.objects.create(
                kind=NoticeSent.Kind.DIGEST,
                key=key,
                user=gm_user,
            )


def _build_rsvp_groups(session: PlaySession) -> dict[str, list[tuple]]:
    """Build RSVP groups for the digest.

    Returns a dict with keys: yes, maybe, no, not_answered.
    Each value is a list of (character, player_name) tuples.
    """
    # Get all characters in the club that are not archived and not dead
    characters = Character.objects.filter(
        club=session.club,
        archived_at__isnull=True,
        died_on__isnull=True,
    ).select_related("owner__user")

    # Get existing RSVPs for this session
    rsvps = {
        rsvp.character_id: rsvp.answer for rsvp in session.rsvps.select_related("character").all()
    }

    yes = []
    maybe = []
    no = []
    not_answered = []

    for character in characters:
        player_name = character.owner.user.display_name or character.owner.user.email
        answer = rsvps.get(character.id)

        if answer == SessionRSVP.Answer.YES:
            yes.append((character, player_name))
        elif answer == SessionRSVP.Answer.MAYBE:
            maybe.append((character, player_name))
        elif answer == SessionRSVP.Answer.NO:
            no.append((character, player_name))
        else:
            not_answered.append((character, player_name))

    return {
        "yes": yes,
        "maybe": maybe,
        "no": no,
        "not_answered": not_answered,
    }


def _is_suppressed(email: str) -> bool:
    """Check if an email is suppressed (do-not-email or .invalid)."""
    normalized = email.strip().lower()
    if normalized.endswith(".invalid"):
        return True
    from mail.models import DoNotEmail

    return DoNotEmail.objects.filter(address=normalized).exists()


# Register the job
register_job("send_digests", send_digests)
