"""Views for creating, editing, and cancelling play sessions."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_POST

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404

from ..forms import SessionForm
from ..models import PlaySession
from ..services import cancel_session, create_sessions, update_session


@admin_or_gm_required
def session_create(request, club_slug):
    """Create a single play session."""
    club = request.club
    membership = request.membership

    if request.method == "POST":
        form = SessionForm(club, membership, data=request.POST)
        if form.is_valid():
            sessions = create_sessions(club, membership, form.cleaned_data)
            messages.success(request, f"Scheduled {len(sessions)} session.")
            return redirect(
                "play_sessions:session_detail",
                club_slug=club.slug,
                pk=sessions[0].pk,
            )
    else:
        form = SessionForm(club, membership)

    try:
        back_url = reverse("play_sessions:calendar")
    except NoReverseMatch:
        back_url = ""

    return render(
        request,
        "play_sessions/session_form.html",
        {
            "form": form,
            "club": club,
            "title": "New session",
            "session": None,
            "back_url": back_url,
        },
    )


@admin_or_gm_required
def session_edit(request, club_slug, pk):
    """Edit a single play session. No past-date check."""
    club = request.club
    membership = request.membership
    session = club_get_object_or_404(request, PlaySession, pk=pk)

    if request.method == "POST":
        form = SessionForm(club, membership, instance=session, data=request.POST)
        if form.is_valid():
            update_session(session, form.cleaned_data)
            messages.success(request, "Session updated.")
            return redirect(
                "play_sessions:session_detail",
                club_slug=club.slug,
                pk=session.pk,
            )
    else:
        form = SessionForm(club, membership, instance=session)

    return render(
        request,
        "play_sessions/session_form.html",
        {
            "form": form,
            "club": club,
            "title": "Edit session",
            "session": session,
            "back_url": reverse("play_sessions:session_detail", args=[club.slug, session.pk]),
        },
    )


@require_POST
@admin_or_gm_required
def session_cancel(request, club_slug, pk):
    """Cancel a single session (POST only)."""
    club = request.club
    session = club_get_object_or_404(request, PlaySession, pk=pk)
    cancel_session(session)
    messages.success(request, "Session cancelled.")
    return redirect(
        "play_sessions:session_detail",
        club_slug=club.slug,
        pk=session.pk,
    )
