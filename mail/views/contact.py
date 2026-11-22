"""Contact email view for club settings."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from accounts.permissions import club_admin_required
from mail.models import ClubMailSettings


@club_admin_required
def contact_email(request, club_slug):
    """Update the club's contact email (club admin only)."""
    club = request.club
    settings, _ = ClubMailSettings.objects.get_or_create(club=club)

    if request.method == "POST":
        email = request.POST.get("contact_email", "").strip().lower()
        if email:
            # Basic email validation
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(email)
            except ValidationError:
                if request.headers.get("HX-Request"):
                    return HttpResponse(
                        render_to_string(
                            "mail/_club_contact_card.html",
                            {
                                "club": club,
                                "settings": settings,
                                "error": "Enter a valid email address.",
                            },
                            request=request,
                        ),
                        status=400,
                    )
                messages.error(request, "Enter a valid email address.")
            else:
                settings.contact_email = email
                settings.save(update_fields=["contact_email"])
                messages.success(request, "Contact email saved.")
        else:
            # Blank is allowed - clear the contact email
            settings.contact_email = ""
            settings.save(update_fields=["contact_email"])
            messages.success(request, "Contact email cleared.")

    # Always render the card partial (for both HTMX and regular requests)
    return render(
        request,
        "mail/_club_contact_card.html",
        {"club": club, "settings": settings},
    )