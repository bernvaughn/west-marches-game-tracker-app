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
    # The embedded mail cards (contact email, test email) need this context on a
    # plain page load, not just after their own HTMX actions.
    from mail.models import ClubMailSettings, EmailMessage
    from mail.service import email_disabled_reason, email_enabled

    from ..models import Membership

    context = {
        "club": club,
        "form": form,
        "settings": ClubMailSettings.objects.get_or_create(club=club)[0],
        "admins": Membership.objects.filter(club=club, is_club_admin=True).select_related("user"),
        "email_on": email_enabled(),
        "disabled_reason": email_disabled_reason(),
        "recent_tests": EmailMessage.objects.filter(club=club, kind="test").order_by("-created")[
            :10
        ],
    }
    return render(request, "accounts/clubs/settings.html", context)
