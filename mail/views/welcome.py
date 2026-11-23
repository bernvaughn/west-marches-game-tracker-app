"""Welcome email views: public set-password and club admin show-link."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_http_methods

from accounts.passwords import ComplexityValidator, PasswordHistoryValidator, save_password_history
from accounts.permissions import club_admin_required
from mail.builders import render_email
from mail.models import EmailMessage
from mail.service import queue_email
from mail.tokens import consume, issue, revoke_older


@require_http_methods(["GET", "POST"])
def welcome_set_password(request, token):
    """Public view: GET shows password form, POST sets password and consumes token."""
    # Peek at the token first (GET doesn't consume)
    from mail.tokens import peek

    peeked = peek(token, "welcome")
    if peeked is None:
        ctx = {"valid": False, "expired": True}
        response = render(request, "mail/welcome_set_password.html", ctx)
        add_never_cache_headers(response)
        return response

    club = peeked.club

    if request.method == "GET":
        ctx = {"valid": True, "token": token, "club": club}
        response = render(request, "mail/welcome_set_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # POST - validate and set password
    password = request.POST.get("password", "")
    confirm = request.POST.get("confirm", "")

    if password != confirm:
        ctx = {"valid": True, "token": token, "error": "Passwords do not match.", "club": club}
        response = render(request, "mail/welcome_set_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # Validate complexity
    validator = ComplexityValidator()
    try:
        validator.validate(password)
    except Exception as e:
        ctx = {"valid": True, "token": token, "error": str(e), "club": club}
        response = render(request, "mail/welcome_set_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # Validate password history
    history_validator = PasswordHistoryValidator()
    try:
        history_validator.validate(password, peeked.user)
    except Exception as e:
        ctx = {"valid": True, "token": token, "error": str(e), "club": club}
        response = render(request, "mail/welcome_set_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # Try to consume the token
    consumed = consume(token, "welcome")
    if consumed is None:
        ctx = {
            "valid": False,
            "error": "This link has already been used or has expired.",
            "club": club,
        }
        response = render(request, "mail/welcome_set_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # Set the password
    with transaction.atomic():
        user = consumed.user
        user.set_password(password)
        user.must_change_password = False
        # Skip the password change notice email (M4)
        user._mail_skip_password_notice = True
        user.save(update_fields=["password", "must_change_password"])
        save_password_history(user, password)

    # Sign out all other sessions by rotating the session key
    # This is done by the update_session_auth_hash call on the current session
    # and the password change invalidates other sessions automatically in Django

    messages.success(request, "Your password has been set. You can now sign in.")
    return redirect("login")


@club_admin_required
@require_http_methods(["POST"])
def welcome_show_link(request, club_slug, message_pk):
    """Club admin view: POST only, shows fresh welcome link once (never cached)."""
    # Find the EmailMessage
    message = get_object_or_404(
        EmailMessage,
        pk=message_pk,
        kind=EmailMessage.Kind.WELCOME,
        club=request.club,
    )

    # Only allow for failed or bounced messages
    if message.status not in (EmailMessage.Status.FAILED, EmailMessage.Status.BOUNCED):
        messages.error(request, "Can only resend welcome email for failed or bounced messages.")
        return redirect("accounts:whitelist", club_slug=request.club.slug)

    user = message.user
    if user is None:
        messages.error(request, "No user associated with this welcome email.")
        return redirect("accounts:whitelist", club_slug=request.club.slug)

    # Revoke older welcome tokens for this user/club
    revoke_older("welcome", user, request.club)

    # Issue a new 7-day welcome token
    raw_token = issue("welcome", user, club=request.club)

    # Build the welcome link (public URL)
    welcome_link = request.build_absolute_uri(f"/mail/welcome/{raw_token}/")

    # Build email content
    subject, text, html = render_email(
        "welcome",
        "welcome",
        {
            "subject": f"Welcome to {request.club.name}",
            "user": user,
            "club": request.club,
            "welcome_link": welcome_link,
        },
        request.club,
    )

    # Queue the email
    result = queue_email(
        kind="welcome",
        to=user.email,
        club=request.club,
        subject=subject,
        text=text,
        html=html,
        user=user,
    )

    if result.status != "queued":
        err = result.message.last_error if result.message else "Unknown error"
        messages.error(
            request,
            "Failed to queue welcome email: "
            f"{err}",
        )
        return redirect("accounts:whitelist", club_slug=request.club.slug)

    # Show the fresh link once, never cached
    ctx = {
        "welcome_link": welcome_link,
        "user": user,
        "club": request.club,
        "message_pk": message_pk,
    }
    response = render(request, "mail/welcome_show_link.html", ctx)
    add_never_cache_headers(response)
    return response


@club_admin_required
@require_http_methods(["POST"])
def welcome_resend(request, club_slug):
    """Club admin view: POST only, resend welcome email for a member."""
    # This view is used from the People page to resend welcome email
    # It expects a membership pk in POST data
    from accounts.models import Membership

    membership_pk = request.POST.get("membership_pk")
    if not membership_pk:
        messages.error(request, "No member selected.")
        return redirect("accounts:whitelist", club_slug=request.club.slug)

    membership = get_object_or_404(Membership, pk=membership_pk, club=request.club)
    user = membership.user

    # Revoke older welcome tokens for this user/club
    revoke_older("welcome", user, request.club)

    # Issue a new 7-day welcome token
    raw_token = issue("welcome", user, club=request.club)

    # Build the welcome link (public URL)
    welcome_link = request.build_absolute_uri(f"/mail/welcome/{raw_token}/")

    # Build email content
    subject, text, html = render_email(
        "welcome",
        "welcome",
        {
            "subject": f"Welcome to {request.club.name}",
            "user": user,
            "club": request.club,
            "welcome_link": welcome_link,
        },
        request.club,
    )

    # Queue the email
    result = queue_email(
        kind="welcome",
        to=user.email,
        club=request.club,
        subject=subject,
        text=text,
        html=html,
        user=user,
    )

    if result.status == "queued":
        messages.success(request, f"Welcome email resent to {user.email}.")
    elif result.status == "refused":
        err = result.message.last_error if result.message else "Address is suppressed"
        messages.warning(
            request,
            "Could not send welcome email: "
            f"{err}.",
        )
    elif result.status == "failed":
        err = result.message.last_error if result.message else "Email is disabled"
        messages.warning(
            request,
            "Could not send welcome email: "
            f"{err}.",
        )

    return redirect("accounts:index", club_slug=request.club.slug)
