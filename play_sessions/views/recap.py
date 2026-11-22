"""Views for the recap feature."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404

from .. import recap_forms
from ..models import PlaySession


@admin_or_gm_required
def recap_edit(request, club_slug, pk):
    """Edit recap and GM notes for a session.

    Only GMs and club admins (and superusers) can access this view.
    Players get 403. Sessions from another club give 404.
    Past, future, and cancelled sessions are all editable.
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)

    if request.method == "POST":
        form = recap_forms.RecapForm(request.POST, instance=session)
        if form.is_valid():
            form.instance.save(update_fields=["recap", "gm_notes", "updated"])
            messages.success(request, "Recap and notes saved.")
            url = reverse("play_sessions:session_detail", kwargs={"club_slug": club_slug, "pk": pk})
            return redirect(f"{url}#section-recap")
    else:
        form = recap_forms.RecapForm(instance=session)

    club = request.club
    can_manage = True  # admin_or_gm_required guarantees this
    cancel_url = reverse("play_sessions:session_detail", kwargs={"club_slug": club_slug, "pk": pk})

    context = {
        "session": session,
        "club": club,
        "can_manage": can_manage,
        "form": form,
        "cancel_url": cancel_url,
    }
    return render(request, "play_sessions/recap_form.html", context)