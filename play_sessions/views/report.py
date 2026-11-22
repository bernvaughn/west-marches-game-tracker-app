"""Views for the attendance report (P8) and its CSV export.

Both views are admin only: ``@club_admin_required`` (superusers pass too).
"""

import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

from accounts.permissions import club_admin_required

from .. import report as report_module


@club_admin_required
def report(request, club_slug):
    """Attendance report page: GET filter form plus character and player tables."""
    club = request.club
    start, end, error = report_module.parse_range(request.GET, club)

    characters = []
    players = []
    if not error:
        characters, players = report_module.report_rows(club, start, end)

    csv_url = reverse("play_sessions:report_csv", kwargs={"club_slug": club.slug})
    if request.GET:
        csv_url += "?" + request.GET.urlencode()

    context = {
        "club": club,
        "start": request.GET.get("start", ""),
        "end": request.GET.get("end", ""),
        "error": error,
        "characters": characters,
        "players": players,
        "csv_url": csv_url,
        "has_filter": bool(request.GET.get("start") or request.GET.get("end")),
    }
    return render(request, "play_sessions/report.html", context)


@club_admin_required
def report_csv(request, club_slug):
    """CSV export of the attendance report with the same filter."""
    club = request.club
    start, end, error = report_module.parse_range(request.GET, club)

    if error:
        return HttpResponse(error, status=400, content_type="text/plain; charset=utf-8")

    characters, players = report_module.report_rows(club, start, end)

    filename = f"attendance-{club.slug}"
    if start:
        filename += f"-{start}"
    if end:
        filename += f"-{end}"
    filename += ".csv"

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["kind", "name", "player", "sessions"])

    for row in characters:
        writer.writerow(
            [
                "character",
                _csv_cell(row["name"]),
                _csv_cell(row["owner"]),
                row["sessions"],
            ]
        )
    for row in players:
        writer.writerow(
            [
                "player",
                _csv_cell(row["name"]),
                _csv_cell(row["name"]),
                row["sessions"],
            ]
        )
    return response


def _csv_cell(value):
    """Guard against CSV formula injection.

    Cells starting with ``= + - @`` are prefixed with ``'`` so
    spreadsheet apps treat them as literal text.
    """
    text = str(value)
    if text and text[0] in "=+-@":
        return "'" + text
    return text
