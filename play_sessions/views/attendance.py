"""Views for attendance feature (P5, P6)."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404

from .. import core
from ..attendance_forms import AttendanceForm, RsvpForClubForm
from ..models import AttendanceChange, PlaySession
from ..services_attendance import attendance_rows, save_attendance


@admin_or_gm_required
def attendance(request, club_slug, pk):
    """Attendance page: GM/admin ticks which characters played.

    GET: renders form with checkboxes for each active character.
    POST: validates and saves attendance.
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)
    club = request.club

    if request.method == "POST":
        form = AttendanceForm(club, request.POST)
        if form.is_valid():
            selected_ids = set(form.cleaned_data["characters"].values_list("pk", flat=True))
            save_attendance(session, selected_ids, request.user, club)
            messages.success(request, "Attendance saved.")
            return redirect("play_sessions:session_detail", club_slug=club.slug, pk=session.pk)
    else:
        rows = attendance_rows(session, club)
        form = AttendanceForm(
            club, initial={"characters": [r["character"] for r in rows if r["checked"]]}
        )

    # Get recent attendance changes (last 20)
    changes = (
        AttendanceChange.objects.filter(session=session)
        .select_related("character", "changed_by")
        .order_by("-changed_at")[:20]
    )

    context = {
        "session": session,
        "club": club,
        "rows": rows if request.method != "POST" else attendance_rows(session, club),
        "form": form,
        "changes": changes,
    }
    return render(request, "play_sessions/attendance.html", context)


@require_POST
@admin_or_gm_required
def rsvp_for(request, club_slug, pk):
    """GM/admin sets an RSVP for any active club character.

    No start-time lock: GM and admin may answer any time.
    Redirects to session detail with a message.
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)
    club = request.club

    form = RsvpForClubForm(club, request.POST)
    if form.is_valid():
        character = form.cleaned_data["character"]
        answer = form.cleaned_data["answer"]
        core.set_rsvp(session, character, answer, request.user)
        messages.success(request, f"RSVP set to {answer} for {character.name}.")
    else:
        messages.error(request, "Invalid RSVP data.")

    return redirect("play_sessions:session_detail", club_slug=club.slug, pk=session.pk)
