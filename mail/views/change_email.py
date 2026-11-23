"""Views for changing email address (E9)."""

from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import render
from django.views import View

from accounts.permissions import club_member_required
from mail.service import email_enabled, queue_email
from mail.tokens import consume, issue, peek


@club_member_required
def change_email(request, club_slug):
    """Club view to request an email change.

    GET: Shows form with current email.
    POST: Validates new email, issues token, queues confirmation email to new address.
    """
    club = request.club
    user = request.user
    current_email = user.email

    if request.method == "GET":
        return render(
            request,
            "mail/change_email.html",
            {"club": club, "current_email": current_email},
        )

    # POST: process new email
    new_email = request.POST.get("new_email", "").strip().lower()

    # Validation
    error = None
    if not new_email:
        error = "Enter an email address."
    elif new_email == current_email.lower():
        error = "This is already your email address."
    else:
        try:
            validate_email(new_email)
        except ValidationError:
            error = "Enter a valid email address."

    # Check if email is already used by another account (case-insensitive)
    if not error:
        from accounts.models import User

        existing_user = User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).first()
        if existing_user:
            # Neutral answer - same as E4 (forgot password)
            # Show success but send nothing
            messages.success(
                request,
                "If that email address is not already in use, a confirmation link has been sent.",
            )
            return render(
                request,
                "mail/change_email.html",
                {"club": club, "current_email": current_email},
            )

    if error:
        return render(
            request,
            "mail/change_email.html",
            {"club": club, "current_email": current_email, "error": error},
            status=400,
        )

    # Check if email is enabled - if not, show neutral answer
    if not email_enabled():
        messages.success(
            request,
            "If that email address is not already in use, a confirmation link has been sent.",
        )
        return render(
            request,
            "mail/change_email.html",
            {"club": club, "current_email": current_email},
        )

    # Issue email_change token (24 hours TTL)
    raw_token = issue(
        purpose="email_change",
        user=user,
        club=club,
        extra={"new_email": new_email, "old_email": current_email},
    )

    # Build confirm URL
    from django.urls import reverse

    confirm_url = request.build_absolute_uri(reverse("mail_public:confirm_email", args=[raw_token]))

    # Queue confirmation email to NEW address
    subject, text, html = build_confirm_email(
        {
            "user": user,
            "club": club,
            "new_email": new_email,
            "confirm_url": confirm_url,
            "site_url": request.build_absolute_uri("/").rstrip("/"),
        }
    )

    result = queue_email(
        kind="email_change",
        to=new_email,
        club=club,
        subject=subject,
        text=text,
        html=html,
        user=user,
    )

    if result.status == "refused":
        # Address is suppressed - neutral answer
        messages.success(
            request,
            "If that email address is not already in use, a confirmation link has been sent.",
        )
    elif result.status == "failed":
        # Email is off for this site - neutral answer
        messages.success(
            request,
            "If that email address is not already in use, a confirmation link has been sent.",
        )
    else:
        messages.success(
            request,
            "A confirmation link has been sent to the new email address. "
            "Your current email address will remain active until you click the link.",
        )

    return render(
        request,
        "mail/change_email.html",
        {"club": club, "current_email": current_email},
    )


class ConfirmEmailView(View):
    """Public view to confirm email change via token.

    GET: Shows confirmation page with new email address.
    POST: Consumes token, changes user's email, sends notice to old address.
    """

    template_name = "mail/confirm_email.html"

    def get(self, request, token):
        """Show confirmation page. Does not consume the token."""
        ot_token = peek(token, "email_change")
        if not ot_token:
            return render(request, self.template_name, {"error": "invalid_or_expired"})

        extra = ot_token.extra or {}
        new_email = extra.get("new_email")
        old_email = extra.get("old_email")

        if not new_email or not old_email:
            return render(request, self.template_name, {"error": "invalid_token_data"})

        # Check if signed-in user differs from token user
        if request.user.is_authenticated and request.user != ot_token.user:
            return render(request, self.template_name, {"error": "not_for_you"})

        context = {
            "token": token,
            "new_email": new_email,
            "old_email": old_email,
            "club": ot_token.club,
            "show_form": True,
        }
        return render(request, self.template_name, context)

    def post(self, request, token):
        """Confirm email change. Consumes token and changes email."""
        ot_token = consume(token, "email_change")
        if not ot_token:
            return render(request, self.template_name, {"error": "invalid_or_expired"})

        extra = ot_token.extra or {}
        new_email = extra.get("new_email")
        old_email = extra.get("old_email")

        if not new_email or not old_email:
            return render(request, self.template_name, {"error": "invalid_token_data"})

        # Check if signed-in user differs from token user
        if request.user.is_authenticated and request.user != ot_token.user:
            return render(request, self.template_name, {"error": "not_for_you"})

        user = ot_token.user
        club = ot_token.club

        # Check if new_email is already used by another account (case-insensitive)
        from accounts.models import User

        existing_user = User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).first()
        if existing_user:
            # Neutral answer - show success but don't change anything
            return render(
                request,
                self.template_name,
                {
                    "error": None,
                    "neutral": True,
                    "message": "If that email address is not already in use, it has been updated.",
                },
            )

        # Change the user's email (which is also their sign-in name). Normalize
        # so the stored email is always lower-cased, matching every other write
        # path and making login case-insensitive.
        with transaction.atomic():
            user.email = new_email.strip().lower()
            user.save(update_fields=["email"])

            # Sign out other sessions (like password reset)
            logout(request)

        # Send "email changed" notice to OLD address
        subject, text, html = build_email_changed_notice(
            {
                "user": user,
                "club": club,
                "old_email": old_email,
                "new_email": new_email,
                "site_url": request.build_absolute_uri("/").rstrip("/"),
            }
        )

        queue_email(
            kind="email_change",
            to=old_email,
            club=club,
            subject=subject,
            text=text,
            html=html,
            user=user,
        )

        # Success - show confirmation page
        context = {
            "error": None,
            "confirmed": True,
            "new_email": new_email,
            "club": club,
            "message": (
                "Your email address has been changed. "
                "You can now sign in with your new email address."
            ),
        }
        return render(request, self.template_name, context)


def build_confirm_email(context: dict) -> tuple[str, str, str]:
    """Build the confirmation email sent to the new address."""
    from mail.builders import render_email

    subject = "Confirm your new email address"
    context["subject"] = subject
    return render_email("email_change", "confirm_email", context, context.get("club"))


def build_email_changed_notice(context: dict) -> tuple[str, str, str]:
    """Build the 'email changed' notice sent to the old address."""
    from mail.builders import render_email

    subject = "Your email address has been changed"
    context["subject"] = subject
    return render_email("email_change", "email_changed", context, context.get("club"))
