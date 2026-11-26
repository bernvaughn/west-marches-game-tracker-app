"""Time formatting helpers for play sessions.

Provides format_session_time() which formats a datetime with the zone's short name
for that specific date (e.g. "7:00 PM EDT", "7:00 PM EST").
"""

from datetime import UTC, datetime

from django.conf import settings

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python < 3.9
    from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def club_zone(club):
    """Return a ZoneInfo for the club's timezone, falling back to settings.TIME_ZONE."""
    try:
        return ZoneInfo(club.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo(getattr(settings, "TIME_ZONE", "UTC"))


def to_club_local(club, dt):
    """Convert an aware UTC datetime to the club's local time.

    Treats naive datetime as UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(club_zone(club))


def _offset_to_str(offset):
    """Convert a timedelta offset to 'UTC±H:MM' or 'UTC±H' string."""
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if minutes == 0:
        return f"UTC{sign}{hours}"
    return f"UTC{sign}{hours}:{minutes:02d}"


def _short_zone_name(dt):
    """Return the short zone name for an aware datetime, or offset fallback."""
    tzname = dt.tzname()
    if tzname and not tzname.startswith(("+", "-")):
        return tzname
    # Offset-like or empty: fall back to UTC±H:MM style
    offset = dt.utcoffset()
    if offset is not None:
        return _offset_to_str(offset)
    return "UTC"


def format_session_time(moment, club):
    """Format a session time with the zone's short name for that date.

    Args:
        moment: datetime (aware or naive). Naive is treated as UTC.
        club: Club instance with a timezone field.

    Returns:
        String like "7:00 PM EDT" or "7:00 PM EST" or "7:00 PM UTC+5:30".
    """
    local = to_club_local(club, moment)
    zone_name = _short_zone_name(local)
    # Format as "7:00 PM EDT" (hour without leading zero on Linux)
    time_str = local.strftime("%-I:%M %p")
    return f"{time_str} {zone_name}"


def timezone_label(iana_name):
    """Return a friendly label for an IANA timezone name.

    Args:
        iana_name: IANA timezone identifier (e.g., "America/New_York").

    Returns:
        Friendly label like "Eastern Time (New York), now EDT".
        Falls back to the IANA name if not in the curated table.
    """
    # Curated table of common zones
    friendly_names = {
        "America/New_York": "Eastern Time (New York)",
        "America/Chicago": "Central Time (Chicago)",
        "America/Denver": "Mountain Time (Denver)",
        "America/Los_Angeles": "Pacific Time (Los Angeles)",
        "America/Toronto": "Eastern Time (Toronto)",
        "Europe/London": "Greenwich Mean Time (London)",
        "Europe/Paris": "Central European Time (Paris)",
        "Asia/Tokyo": "Japan Standard Time (Tokyo)",
        "Australia/Sydney": "Australian Eastern Time (Sydney)",
        "UTC": "Coordinated Universal Time (UTC)",
    }

    friendly = friendly_names.get(iana_name)
    if friendly is None:
        return iana_name

    # Get current short name for this zone
    try:
        zone = ZoneInfo(iana_name)
    except ZoneInfoNotFoundError:
        return iana_name

    # Use current time to determine DST status
    now = datetime.now(UTC)
    local_now = now.astimezone(zone)
    short_name = _short_zone_name(local_now)

    return f"{friendly}, now {short_name}"


def timezone_choices():
    """Return (iana, friendly_label) pairs for form choices.

    The stored value (first element) remains the IANA name.
    The display label (second element) is the friendly label with current short name.
    """
    from zoneinfo import available_timezones

    choices = []
    for name in sorted(available_timezones()):
        label = timezone_label(name)
        choices.append((name, label))
    return choices
