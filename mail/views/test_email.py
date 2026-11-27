"""Test email view for club settings."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import Membership
from accounts.permissions import club_admin_required
from accounts.ratelimit import rate_limit
from mail import service as mail_service
from mail.builders_test import build_test_email
from mail.models import ClubMailSettings, EmailMessage, EmailPayload
from mail.sending import send_now


def _club_test_key(request, club_slug):
    """Rate limit key: per club."""
    return f"club:{club_slug}"


def _card_context(club, request):
    """Build the shared card context for GET and error responses.

    Includes ``can_send`` and ``send_blocked_reason`` so the UI and the send
    result agree on whether a test email can actually be delivered.
    """
    admins = Membership.objects.filter(club=club, is_club_admin=True).select_related("user")
    settings, _ = ClubMailSettings.objects.get_or_create(club=club)
    email_on = mail_service.email_enabled()
    can_send = mail_service.email_can_send()
    return {
        "club": club,
        "settings": settings,
        "admins": admins,
        "email_on": email_on,
        "can_send": can_send,
        "disabled_reason": mail_service.email_disabled_reason(),
        "send_blocked_reason": mail_service.test_email_unavailable_reason(),
        "recent_tests": EmailMessage.objects.filter(club=club, kind="test").order_by("-created")[
            :10
        ],
    }


def _render_card(request, context, status=200):
    """Render the test email card partial (HTMX or full page)."""
    if request.headers.get("HX-Request"):
        return render(request, "mail/_club_test_card.html", context, status=status)
    return HttpResponse(
        render_to_string("mail/_club_test_card.html", context, request=request),
        status=status,
    )


@club_admin_required
@rate_limit(prefix="test_email", limit=5, window=3600, key_func=_club_test_key)
def send_test_email(request, club_slug):
    """Send a test email to an admin of the same club (club admin only)."""
    club = request.club
    context = _card_context(club, request)

    if request.method == "POST":
        # Get selected recipient
        recipient_id = request.POST.get("recipient")
        if not recipient_id:
            context["error"] = "Select a recipient."
            return _render_card(request, context, status=400)
        # Verify recipient is an admin of this club
        try:
            recipient_membership = context["admins"].get(id=recipient_id)
        except Membership.DoesNotExist:
            context["error"] = "Invalid recipient."
            return _render_card(request, context, status=400)

        # A test email cannot be delivered without a real key, even when
        # MAIL_ENABLED is true under DEBUG. Refuse before queueing so the UI
        # and the send result stay honest: no failed row is written.
        if context["email_on"] and not context["can_send"]:
            context["error"] = context["send_blocked_reason"]
            return _render_card(request, context, status=400)

        recipient = recipient_membership.user
        to_address = recipient.email

        # Build test email
        subject, text, html = build_test_email(club, request.user)

        # Queue the email with kind="test" (queue_email handles email_enabled check)
        result = mail_service.queue_email(
            kind="test",
            to=to_address,
            club=club,
            subject=subject,
            text=text,
            html=html,
            reply_to=context["settings"].contact_email or None,
            user=request.user,
        )

        send_result = None
        if result.status == "queued":
            # Attempt an immediate synchronous send so the user sees a
            # definite result. Keep the message QUEUED on failure so the
            # background job can retry (queued fallback for resilience).
            send_result = send_now(result.message)
            if send_result.ok:
                result.message.status = EmailMessage.Status.SENT
                result.message.provider_id = send_result.provider_id
                result.message.sent_at = timezone.now()
                result.message.save(update_fields=["status", "provider_id", "sent_at"])
                # Payload no longer needed once the email is sent.
                try:
                    result.message.payload.delete()
                except EmailPayload.DoesNotExist:
                    pass
                messages.success(
                    request,
                    f"Test email sent to {to_address}. Provider ID: {send_result.provider_id}",
                )
            else:
                # Stay QUEUED for the background retry path.
                result.message.last_error = send_result.error
                result.message.save(update_fields=["last_error"])
                messages.error(
                    request,
                    f"Failed to send test email: {send_result.error}",
                )
        elif result.status == "refused":
            messages.error(request, "Recipient email is suppressed.")
        else:  # failed
            messages.error(request, f"Failed to queue: {result.message.last_error}")

        context["send_result"] = send_result

    # Refresh recent tests after potential new entry
    context["recent_tests"] = EmailMessage.objects.filter(club=club, kind="test").order_by(
        "-created"
    )[:10]

    return _render_card(request, context)
