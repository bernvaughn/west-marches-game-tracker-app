"""View for reminder settings (E5)."""

from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.permissions import club_admin_required
from mail.models import ClubMailSettings

ALLOWED_DAYS = [1, 2, 3, 5, 7]


@club_admin_required
def reminder_settings(request, club_slug):
    """Allow club admins to configure reminder days."""
    club = request.club
    settings_obj, _ = ClubMailSettings.objects.get_or_create(club=club)

    if request.method == "POST":
        selected = request.POST.getlist("reminder_days")
        valid_days = []
        for day_str in selected:
            try:
                day = int(day_str)
                if day in ALLOWED_DAYS:
                    valid_days.append(day)
            except ValueError:
                pass

        # Deduplicate and sort
        settings_obj.reminder_days = sorted(set(valid_days))
        settings_obj.save(update_fields=["reminder_days"])

        if valid_days:
            messages.success(request, "Reminder days saved.")
        else:
            messages.success(request, "Reminder days saved. No reminders will be sent.")

        return redirect("mail:reminder_settings", club_slug=club.slug)

    current_days = settings_obj.reminder_days or [3]
    return render(
        request,
        "mail/reminder_settings.html",
        {
            "club": club,
            "allowed_days": ALLOWED_DAYS,
            "current_days": current_days,
        },
    )
