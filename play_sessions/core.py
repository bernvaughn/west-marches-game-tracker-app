"""Core contract for the play_sessions app.

Exports timezone helpers, permission checks, the section registry,
the attendance_saved signal, feature list, and auto-discovery.
"""

import importlib.util
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.dispatch import Signal
from django.utils import timezone as dj_timezone

try:
    from zoneinfo import ZoneInfo
    from zoneinfo import ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python < 3.9
    from backports.zoneinfo import ZoneInfo
    from backports.zoneinfo import ZoneInfoNotFoundError

FEATURES = ("schedule", "calendar", "rsvp", "attendance", "report", "recap", "settings")

# --- Timezone helpers --------------------------------------------------------


def club_zone(club):
    """Return a ZoneInfo for the club's timezone, falling back to settings.TIME_ZONE."""
    try:
        return ZoneInfo(club.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo(getattr(settings, "TIME_ZONE", "UTC"))


def to_club_local(club, dt):
    """Convert an aware UTC datetime to the club's local time."""
    if dt.tzinfo is None:
        raise ValueError("to_club_local requires an aware datetime")
    return dt.astimezone(club_zone(club))


def from_club_local(club, naive):
    """Convert a naive datetime (in club local time) to aware UTC.

    Rejects aware input. DST gap times resolve with fold=0 (PEP 495).
    """
    if naive.tzinfo is not None:
        raise ValueError("from_club_local requires a naive datetime")
    zone = club_zone(club)
    aware = naive.replace(tzinfo=zone, fold=0)
    return aware.astimezone(dj_timezone.utc)


# --- Permissions -------------------------------------------------------------


def can_manage_sessions(user, club):
    """Return True if the user can create/edit/cancel sessions and take attendance.

    True for club admins, game masters, and superusers.
    """
    if user.is_superuser:
        return True
    from accounts.models import Membership

    membership = Membership.objects.filter(user=user, club=club).first()
    if not membership:
        return False
    return membership.is_club_admin or membership.is_game_master


def character_is_active(character):
    """Return True if the character can RSVP or be marked for attendance.

    Placeholder: the death/archive epic will replace the body.
    """
    return True


# --- RSVP helper -------------------------------------------------------------


def set_rsvp(session, character, answer, by):
    """Create or update an RSVP for a character on a session.

    Args:
        session: PlaySession instance.
        character: Character instance.
        answer: One of "yes", "maybe", "no".
        by: User who is answering (may be different from character owner).

    Returns:
        The created/updated SessionRSVP instance.

    Raises:
        ValueError: if answer is not a valid choice.
    """
    if answer not in SessionRSVP.Answer.values:
        raise ValueError(f"Invalid RSVP answer: {answer}")

    from .models import SessionRSVP

    rsvp, _ = SessionRSVP.objects.update_or_create(
        session=session,
        character=character,
        defaults={"answer": answer, "answered_by": by, "answered_at": dj_timezone.now()},
    )
    return rsvp


# --- Signal ------------------------------------------------------------------


attendance_saved = Signal()
"""Sent after attendance is saved.

Provides: session (PlaySession), characters (list[Character]), by (User).
"""


# --- Section registry --------------------------------------------------------


_sections = {}


def register_session_section(key, order, template, context_fn, visible_fn=None):
    """Register a section for the session detail page.

    Args:
        key: Unique identifier for the section. Re-registering replaces the entry.
        order: Integer sort order (lower first).
        template: Template path to render for this section.
        context_fn: Callable(request, session) -> dict of extra context.
        visible_fn: Optional callable(request, session) -> bool. Defaults to always visible.
    """
    _sections[key] = {
        "key": key,
        "order": order,
        "template": template,
        "context_fn": context_fn,
        "visible_fn": visible_fn or (lambda request, session: True),
    }


def session_sections(request, session):
    """Return visible sections for a session, sorted by (order, key)."""
    visible = [
        s for s in _sections.values() if s["visible_fn"](request, session)
    ]
    visible.sort(key=lambda s: (s["order"], s["key"]))
    return visible


# --- Auto-discovery ----------------------------------------------------------


def discover_module(feature, prefix, package="play_sessions"):
    """Import urls_<feature> or hooks_<feature> from the package.

    Returns the module object if found, None if the module does not exist.
    Raises ImportError if the module exists but fails to import.
    """
    module_name = f"{package}.{prefix}_{feature}"
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_urlpatterns(attr):
    """Collect urlpatterns from all urls_<feature> modules."""
    patterns = []
    for feature in FEATURES:
        module = discover_module(feature, "urls")
        if module and hasattr(module, attr):
            patterns.extend(getattr(module, attr))
    return patterns


def load_hooks():
    """Call register() on all hooks_<feature> modules."""
    for feature in FEATURES:
        module = discover_module(feature, "hooks")
        if module and hasattr(module, "register"):
            module.register()