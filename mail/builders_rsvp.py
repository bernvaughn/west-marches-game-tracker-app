"""Builder for RSVP email extra (E6).

This module provides the build_rsvp_extra function that is registered
as an email extra for the 'reminder' kind.
"""

from datetime import timedelta

from django.utils import timezone

from mail.tokens import issue
from play_sessions import core


def build_rsvp_extra(context: dict) -> tuple[str, str]:
    """Build RSVP links for the session reminder email.

    Context contains: user, club, session, characters (owned by user).
    For each active character, generates three links: Yes, Maybe, No.
    """
    user = context.get("user")
    club = context.get("club")
    session = context.get("session")
    characters = context.get("characters", [])

    if not all([user, club, session]):
        return "", ""

    text_parts = []
    html_parts = []

    for character in characters:
        # Only include active characters (not dead, not archived)
        if not core.character_is_active(character):
            continue

        # Generate tokens for each answer
        yes_token = issue(
            purpose="rsvp",
            user=user,
            club=club,
            ttl=_ttl_until_session_start(session),
            extra={"session_id": session.pk, "character_id": character.pk, "answer": "yes"},
        )
        maybe_token = issue(
            purpose="rsvp",
            user=user,
            club=club,
            ttl=_ttl_until_session_start(session),
            extra={"session_id": session.pk, "character_id": character.pk, "answer": "maybe"},
        )
        no_token = issue(
            purpose="rsvp",
            user=user,
            club=club,
            ttl=_ttl_until_session_start(session),
            extra={"session_id": session.pk, "character_id": character.pk, "answer": "no"},
        )

        # Build URLs
        site_url = context.get("site_url", "")
        base_url = f"{site_url}/mail/rsvp/"

        yes_url = f"{base_url}{yes_token}/"
        maybe_url = f"{base_url}{maybe_token}/"
        no_url = f"{base_url}{no_token}/"

        # Text version
        text_parts.append(f"\n{character.name}:")
        text_parts.append(f"  Yes: {yes_url}")
        text_parts.append(f"  Maybe: {maybe_url}")
        text_parts.append(f"  No: {no_url}")

        # HTML version
        card_style = "margin: 16px 0; padding: 16px; border: 1px solid #e1e4e8; border-radius: 6px;"
        html_parts.append(f'<div style="{card_style}">')
        html_parts.append(f'<strong style="font-size: 16px;">{character.name}</strong>')
        flex_style = "margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;"
        html_parts.append(f'<div style="{flex_style}">')
        html_parts.append(
            f'<a href="{yes_url}" class="button" style="background: #28a745;">Yes</a>'
        )
        html_parts.append(
            f'<a href="{maybe_url}" class="button"'
            f' style="background: #ffc107; color: #24292e;">Maybe</a>'
        )
        html_parts.append(f'<a href="{no_url}" class="button" style="background: #cb2431;">No</a>')
        html_parts.append("</div></div>")

    return "\n".join(text_parts), "\n".join(html_parts)


def _ttl_until_session_start(session) -> timedelta:
    """Calculate TTL until session starts."""
    now = timezone.now()
    if session.starts_at <= now:
        # Session already started, minimum TTL
        return timedelta(minutes=1)
    return session.starts_at - now
