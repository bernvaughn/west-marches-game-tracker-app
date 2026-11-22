"""Views for play session settings."""

from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.permissions import club_admin_required

from ..models import SessionSettings
from ..settings_forms import SessionSettingsForm


@club_admin_required
def session_settings(request, club_slug):
    """Session settings page for club admins."""
    club = request.club
    settings_obj, _ = SessionSettings.objects.get_or_create(club=club)

    if request.method == "POST":
        form = SessionSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Session settings saved.")
            return redirect("play_sessions:settings", club_slug=club.slug)
    else:
        form = SessionSettingsForm(instance=settings_obj)

    # Build cancel URL - prefer calendar if available
    cancel_url = None
    try:
        cancel_url = request.resolver_match.namespace + ":calendar"
    except (AttributeError, KeyError):
        pass

    context = {
        "club": club,
        "form": form,
        "cancel_url": cancel_url,
    }
    return render(request, "play_sessions/settings.html", context)
