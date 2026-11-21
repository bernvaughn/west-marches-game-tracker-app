"""Views for club settings."""

from django.contrib import messages
from django.shortcuts import redirect, render

from ..forms.club_settings import ClubSettingsForm
from ..permissions import club_admin_required


@club_admin_required
def club_settings(request, club_slug):
    """Allow club admins to edit the club's time zone."""
    club = request.club
    if request.method == "POST":
        form = ClubSettingsForm(request.POST, instance=club)
        if form.is_valid():
            club.timezone = form.cleaned_data["timezone"]
            club.save(update_fields=["timezone"])
            messages.success(request, "Time zone saved.")
            return redirect("accounts:club_settings", club_slug=club.slug)
    else:
        form = ClubSettingsForm(instance=club)
    return render(request, "accounts/clubs/settings.html", {"club": club, "form": form})
