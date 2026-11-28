"""Hooks for the attendance report feature.

Registers the sheet section and the admin navigation entry.
Called from ``PlaySessionsConfig.ready()`` via auto-discovery.
"""

from django.urls import NoReverseMatch, reverse

from accounts import navigation
from accounts.apps import is_admin
from player_characters.sheet_sections import register_sheet_section

from .report import sheet_history


def _sheet_context(request, character):
    rows, total = sheet_history(character)
    club = getattr(request, "club", None)
    club_slug = club.slug if club is not None else None
    for row in rows:
        try:
            row["session_url"] = reverse(
                "play_sessions:session_detail",
                kwargs={"club_slug": club_slug, "pk": row["session_id"]},
            )
        except NoReverseMatch:
            row["session_url"] = ""
    return {"history": rows, "history_total": total}


def register():
    register_sheet_section(
        "attendance_history",
        30,
        "play_sessions/_sheet_history.html",
        _sheet_context,
    )
    navigation.register(
        "sessions",
        "Attendance report",
        "play_sessions:report",
        is_admin,
        40,
        icon="clipboard-data",
    )
