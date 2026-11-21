"""Views for creating, editing, and cancelling play sessions."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_POST

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404

from ..forms import SessionForm
from ..models import PlaySession
from ..services import (
    cancel_rest,
    cancel_session,
    create_sessions,
    remaining_in_series,
    update_session,
)


@admin_or_gm_required
def session_create(request, club_slug):
    """Create one or more play sessions."""
    club = request.club
    membership = request.membership

    if request.method == "POST":
        form = SessionForm(club, membership, with_repeat=True, data=request.POST)
        if form.is_valid():
            sessions = create_sessions(club, membership, form.cleaned_data)
            messages.success(request, f"Scheduled {len(sessions)} sessions.")
            return redirect(
                "play_sessions:session_detail",
                club_slug=club.slug,
                pk=sessions[0].pk,
            )
    else:
        form = SessionForm(club, membership, with_repeat=True)

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
        form = SessionForm(
            club,
            membership,
            instance=session,
            with_repeat=False,
            data=request.POST,
        )
        if form.is_valid():
            update_session(session, form.cleaned_data)
            messages.success(request, "Session updated.")
            return redirect(
                "play_sessions:session_detail",
                club_slug=club.slug,
                pk=session.pk,
            )
    else:
        form = SessionForm(club, membership, instance=session, with_repeat=False)

    return render(
        request,
        "play_sessions/session_form.html",
        {
            "form": form,
            "club": club,
            "title": "Edit session",
            "session": session,
            "back_url": reverse(
                "play_sessions:session_detail", args=[club.slug, session.pk]
            ),
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


@admin_or_gm_required
def series_cancel(request, club_slug, pk):
    """Cancel this and all later sessions in a series."""
    club = request.club
    session = club_get_object_or_404(request, PlaySession, pk=pk)

    if not session.series_id:
        raise Http404("This session is not part of a series.")

    if request.method == "POST":
        count = cancel_rest(session)
        messages.success(request, f"Cancelled {count} session(s).")
        return redirect(
            "play_sessions:session_detail",
            club_slug=club.slug,
            pk=session.pk,
        )

    later = remaining_in_series(session)
    count = later.count() + 1

    return render(
        request,
        "play_sessions/series_cancel.html",
        {
            "session": session,
            "club": club,
            "later_sessions": later,
            "count": count,
        },
    )
