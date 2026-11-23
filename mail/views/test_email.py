"""Test email view for club settings."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from accounts.permissions import club_admin_required
from accounts.ratelimit import rate_limit
from mail.builders_test import build_test_email
from mail.models import ClubMailSettings, EmailMessage
from mail.service import email_disabled_reason, email_enabled, queue_email


def _club_test_key(request, club_slug):
    """Rate limit key: per club."""
    return f"club:{club_slug}"


@club_admin_required
@rate_limit(prefix="test_email", limit=5, window=3600, key_func=_club_test_key)
def send_test_email(request, club_slug):
    """Send a test email to an admin of the same club (club admin only)."""
    club = request.club

    # Get club admins for recipient selection
    from accounts.models import Membership

    admins = Membership.objects.filter(club=club, is_club_admin=True).select_related("user")

    # Get or create mail settings
    settings, _ = ClubMailSettings.objects.get_or_create(club=club)

    # Check if email is enabled
    email_on = email_enabled()
    disabled_reason = email_disabled_reason()

    # Get recent test emails for this club (for log display)
    recent_tests = EmailMessage.objects.filter(club=club, kind="test").order_by("-created")[:10]

    # Build context for error responses
    context = {
        "club": club,
        "settings": settings,
        "admins": admins,
        "email_on": email_on,
        "disabled_reason": disabled_reason,
        "recent_tests": recent_tests,
    }

    if request.method == "POST":
        # Get selected recipient
        recipient_id = request.POST.get("recipient")
        if not recipient_id:
            error = "Select a recipient."
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    render_to_string(
                        "mail/_club_test_card.html",
                        {
                            "club": club,
                            "settings": settings,
                            "admins": admins,
                            "email_on": email_on,
                            "disabled_reason": disabled_reason,
                            "error": error,
                            "recent_tests": recent_tests,
                        },
                        request=request,
                    ),
                    status=400,
                )
            error_context = {**context, "error": error}
            return render(request, "mail/_club_test_card.html", error_context, status=400)
        else:
            # Verify recipient is an admin of this club
            try:
                recipient_membership = admins.get(id=recipient_id)
            except Membership.DoesNotExist:
                error = "Invalid recipient."
                if request.headers.get("HX-Request"):
                    return HttpResponse(
                        render_to_string(
                            "mail/_club_test_card.html",
                            {
                                "club": club,
                                "settings": settings,
                                "admins": admins,
                                "email_on": email_on,
                                "disabled_reason": disabled_reason,
                                "error": error,
                                "recent_tests": recent_tests,
                            },
                            request=request,
                        ),
                        status=400,
                    )
                error_context = {**context, "error": error}
                return render(request, "mail/_club_test_card.html", error_context, status=400)
            else:
                recipient = recipient_membership.user
                to_address = recipient.email

                # Build test email
                subject, text, html = build_test_email(club, request.user)

                # Queue the email with kind="test" (queue_email handles email_enabled check)
                result = queue_email(
                    kind="test",
                    to=to_address,
                    club=club,
                    subject=subject,
                    text=text,
                    html=html,
                    reply_to=settings.contact_email or None,
                    user=request.user,
                )

                if result.status == "queued":
                    messages.success(request, "Test email queued.")
                elif result.status == "refused":
                    messages.error(request, "Recipient email is suppressed.")
                else:  # failed
                    messages.error(request, f"Failed to queue: {result.message.last_error}")

    # Refresh recent tests after potential new entry
    context["recent_tests"] = EmailMessage.objects.filter(club=club, kind="test").order_by(
        "-created"
    )[:10]

    if request.headers.get("HX-Request"):
        return render(request, "mail/_club_test_card.html", context)

    return render(request, "mail/_club_test_card.html", context)
