"""Service functions for attendance feature (P5, P6)."""

from django.db import transaction
from django.utils import timezone

from player_characters.models import Character

from . import core
from .models import AttendanceChange, PlaySession, SessionAttendance, SessionRSVP


def active_characters(club):
    """Return active characters for a club, ordered by name.

    Uses select_related to fetch owner and user in one query.
    Filters by core.character_is_active.
    """
    qs = Character.objects.for_club(club).select_related("owner__user")
    return [c for c in qs if core.character_is_active(c)]


def who_is_coming(session):
    """Return grouped RSVP data for the "Who is coming" section.

    Returns a dict with:
    - "groups": list of (answer_label, [rows]) for yes, maybe, no
    - "unanswered": list of player dicts with character names

    Only active characters are considered. Players who have no active
    character with an RSVP for this session are "unanswered".
    """
    active = active_characters(session.club)
    if not active:
        return {"groups": [], "unanswered": []}

    # Get all RSVPs for these characters in this session
    rsvp_qs = SessionRSVP.objects.filter(
        session=session,
        character__in=[c.pk for c in active],
    ).select_related("character", "character__owner__user")
    rsvp_map = {r.character_id: r for r in rsvp_qs}

    # Group characters by answer
    answer_order = [
        (SessionRSVP.Answer.YES, "Yes"),
        (SessionRSVP.Answer.MAYBE, "Maybe"),
        (SessionRSVP.Answer.NO, "No"),
    ]
    groups = []
    answered_character_ids = set()
    for answer_value, answer_label in answer_order:
        rows = []
        for char in active:
            rsvp = rsvp_map.get(char.pk)
            if rsvp and rsvp.answer == answer_value:
                answered_character_ids.add(char.pk)
                rows.append(
                    {
                        "character": char,
                        "level": char.level,
                        "char_class": char.char_class,
                        "player_name": str(char.owner.user),
                    }
                )
        if rows:
            groups.append((answer_label, rows))

    # Find players who have not answered on any of their active characters
    # Group active characters by owner
    owner_to_chars = {}
    for char in active:
        owner_to_chars.setdefault(char.owner_id, []).append(char)

    unanswered = []
    for _owner_id, chars in owner_to_chars.items():
        # Check if any of this owner's active characters has an RSVP
        has_answered = any(c.pk in answered_character_ids for c in chars)
        if not has_answered:
            # Use the first character's owner for player name
            first_char = chars[0]
            player_name = str(first_char.owner.user)
            character_names = ", ".join(c.name for c in chars)
            unanswered.append(
                {
                    "player_name": player_name,
                    "character_names": character_names,
                }
            )

    return {"groups": groups, "unanswered": unanswered}


def attendance_rows(session, club):
    """Return attendance rows for the attendance page.

    For each active character:
    - checked: existing SessionAttendance.played if row exists, else RSVP == yes
    - answer: RSVP answer or None

    Sorted: yes first, then maybe, no, not answered; then by name.
    """
    active = active_characters(club)
    if not active:
        return []

    # Get existing attendance
    att_qs = SessionAttendance.objects.filter(
        session=session,
        character__in=[c.pk for c in active],
    ).select_related("character")
    att_map = {a.character_id: a for a in att_qs}

    # Get RSVPs
    rsvp_qs = SessionRSVP.objects.filter(
        session=session,
        character__in=[c.pk for c in active],
    ).select_related("character")
    rsvp_map = {r.character_id: r for r in rsvp_qs}

    def sort_key(char):
        rsvp = rsvp_map.get(char.pk)
        if rsvp:
            if rsvp.answer == SessionRSVP.Answer.YES:
                return (0, char.name)
            elif rsvp.answer == SessionRSVP.Answer.MAYBE:
                return (1, char.name)
            elif rsvp.answer == SessionRSVP.Answer.NO:
                return (2, char.name)
        return (3, char.name)

    active.sort(key=sort_key)

    rows = []
    for char in active:
        att = att_map.get(char.pk)
        rsvp = rsvp_map.get(char.pk)
        if att:
            checked = att.played
        else:
            checked = rsvp.answer == SessionRSVP.Answer.YES if rsvp else False
        rows.append(
            {
                "character": char,
                "level": char.level,
                "char_class": char.char_class,
                "player_name": str(char.owner.user),
                "checked": checked,
                "answer": rsvp.answer if rsvp else None,
            }
        )
    return rows


def save_attendance(session, selected_ids, by, club):
    """Save attendance for a session.

    Args:
        session: PlaySession instance.
        selected_ids: Set of character PKs that were checked (played=True).
        by: User who is saving.
        club: Club instance (for active character filtering).

    Returns:
        List of Character instances whose attendance was written or changed.

    First save (no SessionAttendance rows exist yet): creates rows for all
    active characters, sends signal with all written characters, writes NO
    AttendanceChange records.

    Subsequent saves: updates existing rows where played changed, creates
    AttendanceChange for each changed row (old_played=None if no row existed
    before). Sends signal once with changed characters (may be empty list).
    """
    active = active_characters(club)
    active_pks = {c.pk for c in active}

    # Filter selected_ids to only active characters
    selected_ids = {pk for pk in selected_ids if pk in active_pks}

    # Check if this is the first save (no attendance rows exist yet)
    first_save = not session.attendance.exists()

    changed_characters = []

    with transaction.atomic():
        for char in active:
            new_played = char.pk in selected_ids
            existing = session.attendance.filter(character=char).first()

            if existing:
                old_played = existing.played
                if old_played != new_played:
                    existing.played = new_played
                    existing.confirmed_by = by
                    existing.confirmed_at = timezone.now()
                    existing.save()
                    if not first_save:
                        AttendanceChange.objects.create(
                            session=session,
                            character=char,
                            old_played=old_played,
                            new_played=new_played,
                            changed_by=by,
                        )
                    changed_characters.append(char)
            else:
                # No row exists yet
                old_played = None
                SessionAttendance.objects.create(
                    session=session,
                    character=char,
                    played=new_played,
                    confirmed_by=by,
                    confirmed_at=timezone.now(),
                )
                if not first_save:
                    AttendanceChange.objects.create(
                        session=session,
                        character=char,
                        old_played=None,
                        new_played=new_played,
                        changed_by=by,
                    )
                changed_characters.append(char)

    # Send signal exactly once after the atomic block
    core.attendance_saved.send(
        sender=PlaySession,
        session=session,
        characters=changed_characters,
        by=by,
    )

    return changed_characters
