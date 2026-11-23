"""Forgot password and password reset views."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_http_methods

from accounts.passwords import ComplexityValidator, PasswordHistoryValidator, save_password_history
from accounts.ratelimit import check_rate_limit, get_client_ip, get_rate_limit_key
from mail.builders import render_email
from mail.service import queue_email
from mail.tokens import consume, issue, peek, revoke_older

User = get_user_model()


NEUTRAL_MESSAGE = (
    "If an account exists for that address, a password reset link has been sent. "
    "The link expires in 1 hour and can be used once."
)


def _forgot_password_rate_limit_key(request, email):
    """Rate limit key for forgot_password: per visitor IP + per email address."""
    # We check both limits in the view, this is just for the visitor IP
    return get_client_ip(request)


@require_http_methods(["GET", "POST"])
def forgot_password(request):
    """Public view: GET shows email form, POST sends reset link."""
    if request.method == "GET":
        return render(request, "mail/forgot_password.html")

    # POST - process the email
    email = request.POST.get("email", "").strip().lower()

    # Rate limit per visitor IP (10/hour)
    visitor_key = get_rate_limit_key(
        "forgot_password_visitor", _forgot_password_rate_limit_key(request, email), 3600
    )
    allowed, remaining, retry_after = check_rate_limit(visitor_key, 10, 3600)
    if not allowed:
        response = render(
            request,
            "mail/forgot_password.html",
            {
                "error": "Too many requests. Please try again later.",
                "retry_after": retry_after,
            },
            status=429,
        )
        return response

    # Rate limit per email address (3/hour)
    address_key = get_rate_limit_key("forgot_password_address", email, 3600)
    allowed, remaining, retry_after = check_rate_limit(address_key, 3, 3600)
    if not allowed:
        response = render(
            request,
            "mail/forgot_password.html",
            {
                "error": "Too many requests for this address. Please try again later.",
                "retry_after": retry_after,
            },
            status=429,
        )
        return response

    # Look up user case-insensitively
    user = User.objects.filter(email__iexact=email).first()

    # If user exists and not suppressed, issue token and queue email
    if user is not None:
        # Check if the address is suppressed (do-not-email or .invalid)
        from mail.suppression import is_suppressed

        if not is_suppressed(user.email):
            # Revoke older password_reset tokens for this user
            revoke_older("password_reset", user)

            # Issue a 1-hour token
            raw_token = issue("password_reset", user)

            # Build the reset link (public URL)
            reset_link = request.build_absolute_uri(f"/mail/reset/{raw_token}/")

            # Build email content
            subject, text, html = render_email(
                "password_reset",
                "password_reset",
                {
                    "subject": "Reset your password",
                    "user": user,
                    "club": None,
                    "reset_link": reset_link,
                },
                None,
            )

            # Queue the email with club=None (no reply-to for users in multiple clubs)
            queue_email(
                kind="password_reset",
                to=user.email,
                club=None,
                subject=subject,
                text=text,
                html=html,
                user=user,
            )

    # Always render the same neutral answer
    return render(
        request,
        "mail/forgot_password.html",
        {"success": NEUTRAL_MESSAGE},
    )


@require_http_methods(["GET", "POST"])
def reset_password(request, token):
    """Public view: GET shows password form, POST resets password and consumes token."""
    # Peek at the token first (GET doesn't consume)
    peeked = peek(token, "password_reset")
    if peeked is None:
        ctx = {"valid": False, "expired": True}
        response = render(request, "mail/reset_password.html", ctx)
        add_never_cache_headers(response)
        return response

    if request.method == "GET":
        ctx = {"valid": True, "token": token}
        response = render(request, "mail/reset_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # POST - validate and reset password
    password = request.POST.get("password", "")
    confirm = request.POST.get("confirm", "")

    if password != confirm:
        ctx = {"valid": True, "token": token, "error": "Passwords do not match."}
        response = render(request, "mail/reset_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # Validate complexity
    validator = ComplexityValidator()
    try:
        validator.validate(password)
    except Exception as e:
        ctx = {"valid": True, "token": token, "error": str(e)}
        response = render(request, "mail/reset_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # Validate password history
    history_validator = PasswordHistoryValidator()
    try:
        history_validator.validate(password, peeked.user)
    except Exception as e:
        ctx = {"valid": True, "token": token, "error": str(e)}
        response = render(request, "mail/reset_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # Try to consume the token
    consumed = consume(token, "password_reset")
    if consumed is None:
        ctx = {
            "valid": False,
            "error": "This link has already been used or has expired.",
        }
        response = render(request, "mail/reset_password.html", ctx)
        add_never_cache_headers(response)
        return response

    # Set the password
    with transaction.atomic():
        user = consumed.user
        user.set_password(password)
        user.must_change_password = False
        # Skip the password change notice email (handled by post_save hook)
        user._mail_skip_password_notice = True
        user.save(update_fields=["password", "must_change_password"])
        save_password_history(user, password)

    # Sign out all other sessions for this user
    _sign_out_other_sessions(user)

    messages.success(request, "Your password has been reset. You can now sign in.")
    return redirect("login")


def _sign_out_other_sessions(user):
    """Delete all Session rows for the given user."""
    # Decode sessions and find those belonging to this user
    user_id_str = str(user.pk)
    sessions_to_delete = []
    for session in Session.objects.all():
        try:
            decoded = session.get_decoded()
            if decoded.get("_auth_user_id") == user_id_str:
                sessions_to_delete.append(session.session_key)
        except Exception:
            continue
    if sessions_to_delete:
        Session.objects.filter(session_key__in=sessions_to_delete).delete()
