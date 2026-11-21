"""Read-only iCalendar feed builder and feed token management.

The .ics is written by hand (RFC 5545, CRLF line ends) with no new dependency.
"""

import secrets
from datetime import timedelta
from django.db import IntegrityError
from django.utils import timezone

from . import core
from .models import PlaySession, SessionSettings


def get_or_create_token(club):
    """Return the club's feed token, creating a long random one on first use.

    Retries once on IntegrityError (token collision).
    """
    try:
        settings = SessionSettings.objects.get(club=club)
    except SessionSettings.DoesNotExist:
        settings = SessionSettings(club=club)
    if not settings.feed_token:
        settings.feed_token = secrets.token_urlsafe(32)
    try:
        settings.save()
    except IntegrityError:
        # Another club took this token at the same time; regenerate once.
        settings.feed_token = secrets.token_urlsafe(32)
        settings.save()
    return settings.feed_token


def reset_token(club):
    """Clear the club's feed token (admin only). The old public link stops working."""
    settings = SessionSettings.objects.get(club=club)
    settings.feed_token = ""
    settings.save(update_fields=["feed_token"])


def _escape_text(value):
    """Escape backslash, semicolon, comma and newline for an iCalendar TEXT value."""
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(content):
    """Fold a content line at 75 octets (RFC 5545), UTF-8 safe."""
    if len(content.encode("utf-8")) <= 75:
        return content
    lines = []
    chunk = content
    while len(chunk.encode("utf-8")) > 75:
        cut = 75
        while cut > 0 and len(chunk[:cut].encode("utf-8")) > 75:
            cut -= 1
        lines.append(chunk[:cut])
        chunk = " " + chunk[cut:]
    lines.append(chunk)
    return "\r\n".join(lines)


def _line(name, value):
    return _fold(f"{name}:{_escape_text(value)}")


def build_ics(club, now):
    """Build the iCalendar text for the club's sessions.

    Window: sessions starting from 180 days ago onward, cancelled ones included.
    Times are UTC. DESCRIPTION carries "Game master: X" plus notes; never recap
    or gm_notes.
    """
    window_start = now - timedelta(days=180)
    sessions = (
        PlaySession.objects.for_club(club)
        .filter(starts_at__gte=window_start)
        .select_related("game_master__user")
        .order_by("starts_at")
    )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//West Marches//Session Calendar//EN",
        "CALSCALE:GREGORIAN",
        _line("X-WR-CALNAME", club.name),
    ]
    for session in sessions:
        started = session.starts_at.strftime("%Y%m%dT%H%M%SZ")
        parts = [
            "BEGIN:VEVENT",
            f"UID:play-session-{session.pk}@{club.slug}",
            f"DTSTAMP:{session.updated.strftime('%Y%m%dT%H%M%SZ')}",
            f"LAST-MODIFIED:{session.updated.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{started}",
            _line("SUMMARY", session.title),
        ]
        if session.ends_at:
            parts.append(f"DTEND:{session.ends_at.strftime('%Y%m%dT%H%M%SZ')}")
        if session.location:
            parts.append(_line("LOCATION", session.location))
        desc_parts = []
        gm = session.game_master
        if gm:
            desc_parts.append(f"Game master: {gm.user.display_name or gm.user.email}")
        if session.notes:
            desc_parts.append(session.notes)
        if desc_parts:
            parts.append(_line("DESCRIPTION", "\n".join(desc_parts)))
        parts.append("STATUS:CANCELLED" if session.cancelled else "STATUS:CONFIRMED")
        parts.append("END:VEVENT")
        lines.extend(parts)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def feed_text(club, now=None):
    """Convenience: build the .ics text for the club (now defaults to now)."""
    return build_ics(club, now or timezone.now())
