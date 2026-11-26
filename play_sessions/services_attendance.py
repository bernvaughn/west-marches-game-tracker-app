"""Service functions for attendance feature (P5, P6, P14, P15)."""

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership
from player_characters.models import Character

from . import core
from .models import (
    AttendanceChange,
    AttendanceHint,
    PlayerRSVP,
    PlaySession,
    SessionAttendance,
)

ANSWER_STATUS = {
    PlayerRSVP.Answer.YES: "success",
    PlayerRSVP.Answer.MAYBE: "warning",
    PlayerRSVP.Answer.NO: "danger",
}


def attendance_history(session, club, limit=20):
    """Return the latest AttendanceChange rows with times in the club zone."""
    changes = (
        AttendanceChange.objects.filter(session=session)
        .select_related("character", "changed_by")
        .order_by("-changed_at")[:limit]
    )
    return [
        {
            "change": change,
            "when": core.to_club_local(club, change.changed_at),
        }
        for change in changes
    ]


def active_characters(club):
    """Return active characters for a club, ordered by name.

    Uses select_related to fetch owner and user in one query.
    Filters by core.character_is_active.
    """
    qs = Character.objects.for_club(club).select_related("owner__user")
    return [c for c in qs if core.character_is_active(c)]


def _members_and_characters(club):
    """Return active characters grouped by their owning membership.

    Returns (members, owner_to_chars): membership objects keyed by id, and
    member id to list of active characters.
    """
    owner_to_chars = {}
    for char in active_characters(club):
        owner_to_chars.setdefault(char.owner_id, []).append(char)
    members = {
        m.id: m
        for m in Membership.objects.for_club(club)
        .filter(id__in=owner_to_chars.keys())
        .select_related("user")
    }
    return members, owner_to_chars


def who_is_coming(session):
    """Return grouped RSVP data for the "Who is coming" section.

    Members (not characters) are grouped by their PlayerRSVP answer: yes,
    maybe, no. Members who have not answered are listed separately. Each
    member's active characters are shown as a plain-text hint next to the name.

    Returns a dict with:
    - "groups": list of (answer_label, [rows]) for yes, maybe, no
    - "unanswered": list of member rows
    - "hinted_pks": character PKs that have an AttendanceHint
    """
    members, owner_to_chars = _members_and_characters(session.club)
    if not owner_to_chars:
        return {"groups": [], "unanswered": [], "hinted_pks": []}

    rsvp_map = {
        r.member_id: r
        for r in PlayerRSVP.objects.filter(session=session).select_related("member__user")
    }
    hinted_pks = list(
        AttendanceHint.objects.filter(session=session).values_list("character_id", flat=True)
    )

    member_rows = []
    for member_id, chars in owner_to_chars.items():
        member = members.get(member_id)
        if member is None:
            continue
        rsvp = rsvp_map.get(member_id)
        member_rows.append(
            {
                "member": member,
                "player_name": str(member.user),
                "characters": chars,
                "character_names": ", ".join(char.name for char in chars),
                "answer": rsvp.answer if rsvp else None,
                "answer_label": rsvp.get_answer_display() if rsvp else None,
            }
        )
    member_rows.sort(key=lambda row: row["player_name"])

    answer_order = [
        (PlayerRSVP.Answer.YES, "Yes"),
        (PlayerRSVP.Answer.MAYBE, "Maybe"),
        (PlayerRSVP.Answer.NO, "No"),
    ]
    groups = []
    answered_member_ids = set()
    for answer_value, answer_label in answer_order:
        rows = [row for row in member_rows if row["answer"] == answer_value]
        if rows:
            answered_member_ids.update(row["member"].id for row in rows)
            groups.append((answer_label, rows))

    unanswered = [row for row in member_rows if row["member"].id not in answered_member_ids]

    return {
        "groups": groups,
        "unanswered": unanswered,
        "hinted_pks": hinted_pks,
    }


def attendance_rows(session, club):
    """Return attendance rows for the attendance page.

    Starts from the members who answered yes. One row per member, listing that
    member's active characters as checkboxes. None are ticked at first unless an
    existing attendance row or an AttendanceHint says otherwise.

    Each row:
    - "member", "player_name": the member
    - "characters": list of {"character", "checked"} dicts
    - "answer"/"answer_label"/"answer_status": the member's RSVP answer

    Sorted by member name.
    """
    active = active_characters(club)
    if not active:
        return []

    active_pks = {c.pk for c in active}
    yes_member_ids = set(
        PlayerRSVP.objects.filter(session=session, answer=PlayerRSVP.Answer.YES).values_list(
            "member_id", flat=True
        )
    )

    _, owner_to_chars = _members_and_characters(club)

    att_qs = SessionAttendance.objects.filter(
        session=session,
        character__in=list(active_pks),
    ).select_related("character")
    att_map = {a.character_id: a for a in att_qs}

    hinted_pks = set(
        AttendanceHint.objects.filter(session=session, character__in=list(active_pks)).values_list(
            "character_id", flat=True
        )
    )

    rsvp_map = {
        r.member_id: r
        for r in PlayerRSVP.objects.filter(session=session, member_id__in=yes_member_ids)
    }

    members = {
        m.id: m
        for m in Membership.objects.for_club(club)
        .filter(id__in=yes_member_ids)
        .select_related("user")
    }

    rows = []
    for member_id in yes_member_ids:
        member = members.get(member_id)
        if member is None:
            continue
        rsvp = rsvp_map.get(member_id)
        char_rows = []
        for char in owner_to_chars.get(member_id, []):
            att = att_map.get(char.pk)
            if att is not None:
                checked = att.played
            else:
                checked = char.pk in hinted_pks
            char_rows.append(
                {
                    "character": char,
                    "checked": checked,
                }
            )
        rows.append(
            {
                "member": member,
                "player_name": str(member.user),
                "characters": char_rows,
                "answer": rsvp.answer if rsvp else None,
                "answer_label": rsvp.get_answer_display() if rsvp else None,
                "answer_status": ANSWER_STATUS.get(rsvp.answer, "neutral") if rsvp else "neutral",
            }
        )

    rows.sort(key=lambda row: row["player_name"])
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

    Scope: the active characters of members who answered yes (including
    never-answered members a manager added as yes). Characters of members who
    answered maybe/no or never answered are never written here.

    First save (no SessionAttendance rows exist yet): creates rows for all
    in-scope characters, sends signal with all written characters, writes NO
    AttendanceChange records. Any AttendanceHint entries are removed.

    Subsequent saves: updates existing rows where played changed, creates
    AttendanceChange for each changed row (old_played=None if no row existed
    before). Sends signal once with changed characters (may be empty list).
    AttendanceHint entries are removed on every confirm.
    """
    active = active_characters(club)
    active_pks = {c.pk for c in active}

    # Filter selected_ids to only active characters
    selected_ids = {pk for pk in selected_ids if pk in active_pks}

    yes_member_ids = set(
        PlayerRSVP.objects.filter(session=session, answer=PlayerRSVP.Answer.YES).values_list(
            "member_id", flat=True
        )
    )
    scope = [c for c in active if c.owner_id in yes_member_ids]

    # Check if this is the first save (no attendance rows exist yet)
    first_save = not session.attendance.exists()

    changed_characters = []

    with transaction.atomic():
        for char in scope:
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

        # Hints only pre-tick the checkbox: once attendance is confirmed they
        # are removed and never become SessionAttendance rows.
        AttendanceHint.objects.filter(session=session).delete()

    # Send signal exactly once after the atomic block
    core.attendance_saved.send(
        sender=PlaySession,
        session=session,
        characters=changed_characters,
        by=by,
    )

    return changed_characters


def set_player_rsvp(session, member, answer, by):
    """Create or update a per-player (member) RSVP for a session.

    Args:
        session: PlaySession instance.
        member: Membership instance answering.
        answer: One of "yes", "maybe", "no".
        by: User who is answering (may be different from the member's user).

    Returns:
        The created/updated PlayerRSVP instance.

    Raises:
        ValueError: if answer is not a valid choice.
    """
    if answer not in PlayerRSVP.Answer.values:
        raise ValueError(f"Invalid RSVP answer: {answer}")

    rsvp, _ = PlayerRSVP.objects.update_or_create(
        session=session,
        member=member,
        defaults={"answer": answer, "answered_by": by, "answered_at": timezone.now()},
    )
    return rsvp
