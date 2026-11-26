"""Job function for sending Game Master digests (E7).

This module provides the send_digests() function that runs periodically
to send digests to game masters about upcoming sessions.
"""

from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership
from mail.builders_digest import build_digest
from mail.jobs import register_job
from mail.models import EmailMessage, EmailPreference, NoticeSent
from mail.service import queue_email
from play_sessions.models import PlayerRSVP, PlaySession
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
    Each value is a list of (membership, active_character_names) tuples.
    Members with no active characters are included with an empty name list.
    """
    # Active (non-archived, non-dead) character names per member, as hint text
    characters = Character.objects.filter(
        club=session.club,
        archived_at__isnull=True,
        died_on__isnull=True,
    ).select_related("owner")

    char_names_by_member: dict[int, list[str]] = defaultdict(list)
    for character in characters:
        char_names_by_member[character.owner_id].append(character.name)

    # Existing per-player RSVPs for this session
    rsvps = {
        rsvp.member_id: rsvp.answer for rsvp in session.player_rsvps.select_related("member").all()
    }

    yes = []
    maybe = []
    no = []
    not_answered = []

    # Every club member appears in exactly one group
    memberships = Membership.objects.filter(club=session.club).distinct().select_related("user")

    for membership in memberships:
        answer = rsvps.get(membership.id)
        char_names = char_names_by_member.get(membership.id, [])
        item = (membership, char_names)

        if answer == PlayerRSVP.Answer.YES:
            yes.append(item)
        elif answer == PlayerRSVP.Answer.MAYBE:
            maybe.append(item)
        elif answer == PlayerRSVP.Answer.NO:
            no.append(item)
        else:
            not_answered.append(item)

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
