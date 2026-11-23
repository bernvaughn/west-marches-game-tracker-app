"""Email preferences views (E8/M9).

- preferences: Club page at c/<club_slug>/mail/preferences/
- unsubscribe: Public page at /mail/unsubscribe/<token>/
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_http_methods

from accounts.permissions import club_member_required
from mail.models import EmailPreference
from mail.suppression import is_suppressed
from mail.tokens import consume, peek

# Email kind configuration
KIND_CONFIG = {
    "welcome": {
        "label": "Welcome email",
        "description": "Sent when you're added to a club. Required for account setup.",
        "always_on": True,
    },
    "password_reset": {
        "label": "Password reset email",
        "description": "Sent when you request a password reset. Required for account recovery.",
        "always_on": True,
    },
    "reminder": {
        "label": "Session reminders",
        "description": "Reminders before upcoming play sessions.",
        "always_on": False,
    },
    "notice": {
        "label": "Session notices (cancelled/changed)",
        "description": "Notifications when a session is cancelled or changed.",
        "always_on": False,
    },
    "digest": {
        "label": "GM session digest",
        "description": "Daily digest of RSVPs for sessions you GM (game masters only).",
        "always_on": False,
        "gm_only": True,
    },
}

KIND_ORDER = ["welcome", "password_reset", "reminder", "notice", "digest"]


@club_member_required
@require_http_methods(["GET", "POST"])
def preferences(request, club_slug):
    """Club page: list optional kinds per club with switches.

    Welcome and password emails are always on with no switch.
    Optional kinds (reminder, notice, digest) have toggle switches.
    GM digest is shown only to game masters.
    If user's email is suppressed, shows "email is off for you" with no switches.
    POST toggles exactly one kind for that membership.
    """
    club = request.club
    user = request.user
    membership = request.membership

    # Check if email is suppressed for this user
    suppressed = is_suppressed(user.email)

    if request.method == "POST" and not suppressed:
        # Handle toggle for exactly one kind
        kind = request.POST.get("kind")
        if kind in KIND_CONFIG and not KIND_CONFIG[kind]["always_on"]:
            # Verify GM-only restriction
            if KIND_CONFIG[kind].get("gm_only") and not membership.is_game_master:
                messages.error(request, "You don't have permission to change this setting.")
            else:
                enabled = request.POST.get("enabled") == "on"
                EmailPreference.objects.update_or_create(
                    membership=membership,
                    kind=kind,
                    defaults={"enabled": enabled},
                )
                action = "enabled" if enabled else "disabled"
                messages.success(request, f"{KIND_CONFIG[kind]['label']} {action}.")
        return redirect("mail:preferences", club_slug=club.slug)

    # Build list of kinds with current preference state
    kinds = []
    for kind_key in KIND_ORDER:
        config = KIND_CONFIG[kind_key]
        # Skip GM-only kinds for non-GMs
        if config.get("gm_only") and not membership.is_game_master:
            continue

        if config["always_on"]:
            enabled = True
        else:
            try:
                pref = EmailPreference.objects.get(membership=membership, kind=kind_key)
                enabled = pref.enabled
            except EmailPreference.DoesNotExist:
                # Default: on for reminder/notice, off for digest
                enabled = kind_key != "digest"

        kinds.append(
            {
                "key": kind_key,
                "label": config["label"],
                "description": config["description"],
                "enabled": enabled,
                "always_on": config["always_on"],
            }
        )

    ctx = {
        "club": club,
        "kinds": kinds,
        "suppressed": suppressed,
        "user_email": user.email,
    }
    response = render(request, "mail/preferences.html", ctx)
    add_never_cache_headers(response)
    return response


@require_http_methods(["GET", "POST"])
def unsubscribe(request, token):
    """Public unsubscribe page: GET shows confirm, POST consumes token and disables.

    Works signed out. GET peeks (never consumes). POST consumes (single use, atomic).
    Invalid/expired token shows error page.
    """
    # Peek at the token first (GET doesn't consume)
    peeked = peek(token, "unsubscribe")

    if peeked is None:
        ctx = {"valid": False, "expired": True}
        response = render(request, "mail/unsubscribe.html", ctx)
        add_never_cache_headers(response)
        return response

    # Extract kind and membership_id from token extra
    # kind is the EmailPreference.Kind value ("reminder", "notice", "digest")
    extra = peeked.extra or {}
    kind = extra.get("kind")
    membership_id = extra.get("membership_id")

    if not kind or not membership_id:
        ctx = {"valid": False, "error": "Invalid unsubscribe link."}
        response = render(request, "mail/unsubscribe.html", ctx)
        add_never_cache_headers(response)
        return response

    # Get kind display name (preference kind -> display)
    kind_names = {
        "reminder": "session reminders",
        "notice": "session notices (cancelled/changed)",
        "digest": "GM digests",
    }
    display = kind_names.get(kind, kind)

    if request.method == "GET":
        # Show confirmation page
        ctx = {"valid": True, "kind": kind, "display": display, "token": token}
        response = render(request, "mail/unsubscribe.html", ctx)
        add_never_cache_headers(response)
        return response

    # POST - consume token and disable preference
    consumed = consume(token, "unsubscribe")
    if consumed is None:
        ctx = {
            "valid": False,
            "error": "This unsubscribe link has already been used or has expired.",
        }
        response = render(request, "mail/unsubscribe.html", ctx)
        add_never_cache_headers(response)
        return response

    # Disable the preference for the membership
    from accounts.models import Membership

    try:
        membership = Membership.objects.get(pk=membership_id)
        EmailPreference.objects.update_or_create(
            membership=membership,
            kind=kind,
            defaults={"enabled": False},
        )
        ctx = {"success": True, "display": display}
        response = render(request, "mail/unsubscribe.html", ctx)
        add_never_cache_headers(response)
        return response
    except Membership.DoesNotExist:
        ctx = {"valid": False, "error": "Could not find the associated membership."}
        response = render(request, "mail/unsubscribe.html", ctx)
        add_never_cache_headers(response)
        return response
