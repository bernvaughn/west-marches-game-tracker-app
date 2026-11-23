"""Builder for Game Master digest email (E7)."""

from mail.builders import render_email
from play_sessions.core import to_club_local


def build_digest(club, session, game_master_membership, rsvp_groups) -> tuple[str, str, str]:
    """Build the Game Master digest email content.

    Args:
        club: Club instance.
        session: PlaySession instance.
        game_master_membership: Membership of the game master.
        rsvp_groups: Dict with keys 'yes', 'maybe', 'no', 'not_answered'.
            Each value is a list of (character, player_name) tuples.

    Returns:
        Tuple of (subject, text, html).
    """
    # Convert session time to club timezone
    local_start = to_club_local(club, session.starts_at)
    local_end = to_club_local(club, session.ends_at) if session.ends_at else None

    context = {
        "club": club,
        "session": session,
        "game_master": game_master_membership,
        "local_start": local_start,
        "local_end": local_end,
        "rsvp_groups": rsvp_groups,
        "subject": f"Session digest: {session.title}",
    }

    return render_email("digest", "gm_digest", context, club)
