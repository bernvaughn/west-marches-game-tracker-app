"""Views for attendance feature (P5, P6, P14, P15)."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Membership
from accounts.permissions import admin_or_gm_required, club_member_required
from accounts.scoping import club_get_object_or_404
from player_characters.models import Character

from .. import core
from ..attendance_forms import AttendanceForm, RsvpForMemberForm
from ..models import AttendanceHint, PlayerRSVP, PlaySession
from ..services_attendance import (
    attendance_history,
    attendance_rows,
    save_attendance,
    set_player_rsvp,
)


@admin_or_gm_required
def attendance(request, club_slug, pk):
    """Attendance page: GM/admin ticks which of each yes member's characters played.

    GET: renders per-member rows with active character checkboxes (none ticked at
    first, unless an AttendanceHint pre-ticks one).
    POST: either adds any member who is not already "yes" as attending (recorded as a yes
    RSVP by the GM), or saves the ticked characters as SessionAttendance rows.
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)
    club = request.club
    session_started = session.starts_at <= timezone.now()
    attendance_confirmed = session.attendance.exists()
    hinted_pks = set(
        AttendanceHint.objects.filter(session=session).values_list("character_id", flat=True)
    )

    if request.method == "POST":
        form = AttendanceForm(club, session, request.POST)

        # Adding a member who is not already "yes" records them as a yes RSVP
        # by the GM; their characters then appear on the page to be ticked.
        if request.POST.get("add_member"):
            member_id = request.POST.get("add_member")
            try:
                member = Membership.objects.for_club(club).get(pk=member_id)
            except (Membership.DoesNotExist, ValueError, TypeError):
                member = None
            if member is None:
                messages.error(request, "That member is not in this club.")
            elif PlayerRSVP.objects.filter(
                session=session, member=member, answer=PlayerRSVP.Answer.YES
            ).exists():
                messages.info(request, f"{member.user} is already marked as attending.")
            elif form.fields["add_member"].queryset.filter(pk=member_id).exists():
                set_player_rsvp(session, member, PlayerRSVP.Answer.YES, request.user)
                messages.success(request, f"{member.user} added as attending.")
            else:
                messages.error(request, "That member cannot be added as attending.")
            return redirect("play_sessions:attendance", club_slug=club.slug, pk=session.pk)

        if form.is_valid():
            selected_ids = set()
            for name in form.member_field_names():
                for char in form.cleaned_data.get(name) or []:
                    selected_ids.add(char.pk)
            save_attendance(session, selected_ids, request.user, club)
            messages.success(request, "Attendance saved.")
            return redirect("play_sessions:session_detail", club_slug=club.slug, pk=session.pk)
    else:
        form = AttendanceForm(club, session)

    rows = attendance_rows(session, club)
    context = {
        "session": session,
        "club": club,
        "rows": rows,
        "form": form,
        "history": attendance_history(session, club),
        "session_started": session_started,
        "attendance_confirmed": attendance_confirmed,
        "hinted_pks": hinted_pks,
    }
    return render(request, "play_sessions/attendance.html", context)


@require_POST
@admin_or_gm_required
def rsvp_for(request, club_slug, pk):
    """GM/admin sets a per-player RSVP for any club member.

    No start-time lock: GM and admin may answer any time.
    Redirects to session detail with a message.
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)
    club = request.club

    form = RsvpForMemberForm(club, request.POST)
    if form.is_valid():
        member = form.cleaned_data["member"]
        set_player_rsvp(session, member, form.cleaned_data["answer"], request.user)
        messages.success(request, f"RSVP set to {form.cleaned_data['answer']} for {member.user}.")
    else:
        messages.error(request, "Invalid RSVP data.")

    return redirect("play_sessions:session_detail", club_slug=club.slug, pk=session.pk)


@require_POST
@club_member_required
def bringing(request, club_slug, pk):
    """Player hints they are bringing a character to the session.

    Creates an AttendanceHint that pre-ticks the attendance checkbox for the GM.
    Never creates a SessionAttendance row. Only allowed after the session has
    started and before attendance is confirmed.
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)
    club = request.club

    if session.starts_at > timezone.now():
        return HttpResponseBadRequest("The session has not started yet.")
    if session.attendance.exists():
        return HttpResponseBadRequest("Attendance has already been confirmed.")

    character_id = request.POST.get("character")
    if not character_id:
        return HttpResponseBadRequest("No character selected.")
    try:
        character = club_get_object_or_404(request, Character, pk=character_id)
    except (ValueError, TypeError):
        return HttpResponseBadRequest("No character selected.")

    membership = request.membership
    is_owner = membership is not None and character.owner_id == membership.id
    if not (is_owner or core.can_manage_sessions(request.user, club)):
        raise PermissionDenied("You can only hint for your own characters.")
    if not core.character_is_active(character):
        return HttpResponseBadRequest("That character is not active.")

    AttendanceHint.objects.get_or_create(session=session, character=character)

    html = render_to_string(
        "play_sessions/_bringing_button.html",
        {"session": session, "character": character, "hinted": True},
        request=request,
    )
    return HttpResponse(html)
