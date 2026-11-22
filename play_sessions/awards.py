"""Signal receiver for attendance awards."""

import logging

from django.contrib import messages
from django.db import transaction

from downtime.services import InsufficientPoints
from downtime.services import award as downtime_award
from play_sessions import core
from play_sessions.models import SessionAttendance, SessionAward, SessionSettings

logger = logging.getLogger(__name__)


def apply_attendance_awards(sender, session, characters, by, request=None, **kwargs):
    """Apply downtime point awards based on attendance.

    Args:
        sender: Signal sender.
        session: PlaySession instance.
        characters: List of Character instances whose attendance was saved.
        by: User who confirmed attendance.
        request: Optional HttpRequest for messages framework.

    Returns:
        List of notice strings (warnings for the GM).
    """
    notices = []

    # Get award_points from SessionSettings
    settings_obj = SessionSettings.objects.filter(club=session.club).first()
    award_points = settings_obj.award_points if settings_obj else 0

    if award_points == 0:
        return notices

    # Load played flags from SessionAttendance
    attendance_qs = SessionAttendance.objects.filter(session=session).select_related("character")
    played_map = {att.character_id: att.played for att in attendance_qs}

    # Deduplicate characters by pk
    unique_characters = {}
    for char in characters:
        unique_characters.setdefault(char.pk, char)

    for character in unique_characters.values():
        _sync_character(session, character, award_points, played_map, by, request, notices)

    return notices


def _sync_character(session, character, award_points, played_map, by, request, notices):
    """Sync a single character's award based on attendance."""
    played = played_map.get(character.pk, False)
    wanted = award_points if played else 0

    with transaction.atomic():
        award_row, _ = SessionAward.objects.select_for_update().get_or_create(
            session=session,
            character=character,
            defaults={"points": 0},
        )

        delta = wanted - award_row.points
        if delta == 0:
            return  # Second confirmation awards nothing

        # Use a savepoint for the award operation
        try:
            with transaction.atomic():
                _apply_award_delta(session, character, delta, award_row, by)
        except InsufficientPoints as e:
            # Savepoint rolled back, SessionAward unchanged
            notice = str(e)
            notices.append(notice)
            logger.warning(notice)
            if request:
                messages.warning(request, notice)


def _apply_award_delta(session, character, delta, award_row, by):
    """Apply the delta through downtime award service and update SessionAward."""
    # Determine note based on delta sign
    local_date = core.to_club_local(session.club, session.starts_at).date()
    if delta > 0:
        note = f"Attended {session.title} on {local_date}"
    else:
        note = f"Removed: Attended {session.title} on {local_date}"

    source = f"play_session:{session.pk}"

    downtime_award(
        characters=character,
        delta=delta,
        note=note,
        by=by,
        kind="award",
        source=source,
        club=session.club,
    )

    award_row.points = award_row.points + delta
    award_row.save()
