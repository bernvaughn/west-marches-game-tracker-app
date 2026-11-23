from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_http_methods

from mail.builders import render_email
from mail.service import queue_email
from mail.tokens import issue, revoke_older
from player_characters.models import Character

from ..forms.people import RolesForm, WhitelistForm
from ..htmx import hx_response, is_htmx, render_modal_or_page
from ..models import Membership, WhitelistEntry
from ..passwords import get_or_create_member
from ..permissions import can_see_email, club_admin_required, club_member_required
from ..ratelimit import rate_limit
from ..scoping import club_get_object_or_404, club_queryset


@club_member_required
def member_list(request, club_slug):
    members = (
        club_queryset(request, Membership)
        .select_related("user")
        .prefetch_related("characters")
        .order_by("user__display_name", "user__email")
    )
    show_email = can_see_email(request.user, request.club)
    ctx = {"members": members, "show_email": show_email, "table_cols": 5 if show_email else 3}
    return render(request, "accounts/people/member_list.html", ctx)


def _whitelist_page(request, form, **extra):
    entries = club_queryset(request, WhitelistEntry).order_by("email")
    ctx = {"form": form, "entries": entries, **extra}
    return render(request, "accounts/people/whitelist.html", ctx)


def _queue_welcome_email(club, user, request_user):
    """Queue a welcome email with a sign-in link for the user.

    Returns (status, message, token_or_None) where status is "queued", "refused", or "failed".
    """
    # Revoke older welcome tokens for this user/club
    revoke_older("welcome", user, club)

    # Issue a new 7-day welcome token
    raw_token = issue("welcome", user, club=club)

    # Build the welcome link (public URL)
    from django.urls import reverse

    welcome_link = request_user.build_absolute_uri(
        reverse("mail_public:welcome_set_password", args=[raw_token])
    )

    # Build email content
    subject, text, html = render_email(
        "welcome",
        "welcome",
        {
            "subject": f"Welcome to {club.name}",
            "user": user,
            "club": club,
            "welcome_link": welcome_link,
        },
        club,
    )

    # Queue the email
    result = queue_email(
        kind="welcome",
        to=user.email,
        club=club,
        subject=subject,
        text=text,
        html=html,
        user=user,
    )

    return result.status, result.message, raw_token if result.status == "queued" else None


@club_admin_required
@rate_limit(
    prefix="whitelist",
    limit=settings.RATELIMIT_PASSWORD_ATTEMPTS,
    window=settings.RATELIMIT_PASSWORD_WINDOW,
    key_func=lambda req, club_slug: str(req.user.id),
)
def whitelist(request, club_slug):
    if request.method != "POST":
        return _whitelist_page(request, WhitelistForm())
    form = WhitelistForm(request.POST)
    if not form.is_valid():
        return _whitelist_page(request, form)
    data = form.cleaned_data
    email = data["email"]
    if Membership.objects.filter(club=request.club, user__email__iexact=email).exists():
        messages.info(request, f"{email} is already a member of this club.")
        return redirect("accounts:whitelist", club_slug=request.club.slug)

    send_welcome_link = data.get("send_welcome_link", False)

    with transaction.atomic():
        membership, temp = get_or_create_member(
            request.club,
            email,
            data["display_name"],
            is_club_admin=data["is_club_admin"],
            is_game_master=data["is_game_master"],
        )
        if data["character_name"].strip():
            Character.objects.create(
                club=request.club, owner=membership, name=data["character_name"].strip()
            )

    # Existing account added to club - send "added_to_club" email (no link)
    if temp is None:
        # Queue the "added to club" email
        subject, text, html = render_email(
            "added_to_club",
            "added_to_club",
            {
                "subject": f"You've been added to {request.club.name}",
                "user": membership.user,
                "club": request.club,
            },
            request.club,
        )
        result = queue_email(
            kind="welcome",
            to=membership.user.email,
            club=request.club,
            subject=subject,
            text=text,
            html=html,
            user=membership.user,
        )
        if result.status == "refused":
            err = (
                result.message.last_error
                if result.message
                else 'Email is disabled or address is suppressed'
            )
            messages.warning(
                request,
                "Could not send notification: "
                f"{err}."
            )
        elif result.status == "failed":
            messages.warning(
                request,
                "Could not send notification: "
                f"{result.message.last_error if result.message else 'Email is disabled'}.",
            )
        messages.success(request, f"{email} already had an account; added to this club.")
        return redirect("accounts:whitelist", club_slug=request.club.slug)

    # New account created - check if we should send welcome link
    if send_welcome_link:
        status, message, token = _queue_welcome_email(request.club, membership.user, request)
        if status == "queued":
            messages.success(
                request,
                "Welcome email sent to "
                f"{email} with a 7-day sign-in link. "
                "No temporary password was shown.",
            )
            return redirect("accounts:whitelist", club_slug=request.club.slug)
        elif status == "refused":
            messages.warning(
                request,
                "Could not send welcome email: "
                f"{message.last_error if message else 'Address is suppressed'}. "
                f"Temporary password shown below.",
            )
        elif status == "failed":
            messages.warning(
                request,
                "Could not send welcome email: "
                f"{message.last_error if message else 'Email is disabled'}. "
                f"Temporary password shown below.",
            )
        # Fall through to show temporary password

    # Default behavior: show temporary password
    response = _whitelist_page(
        request, WhitelistForm(), temp_password=temp, temp_user=membership.user
    )
    add_never_cache_headers(response)
    return response


class _LastAdmin(Exception):
    """Raised inside the atomic block when a change would leave the club with no admin."""


@club_admin_required
@require_http_methods(["GET", "POST"])
def member_roles(request, club_slug, pk):
    membership = club_get_object_or_404(request, Membership, pk=pk)
    who = membership.user.display_name or membership.user.email

    if request.method == "POST":
        form = RolesForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    memberships = list(
                        Membership.objects.select_for_update().filter(club=request.club)
                    )
                    target = next(m for m in memberships if m.pk == membership.pk)
                    was_admin = target.is_club_admin
                    target.is_club_admin = form.cleaned_data["is_club_admin"]
                    target.is_game_master = form.cleaned_data["is_game_master"]
                    admins = sum(1 for m in memberships if m.is_club_admin)
                    if was_admin and not target.is_club_admin and admins == 0:
                        raise _LastAdmin(
                            "This club needs at least one club admin. "
                            "Make someone else a club admin first."
                        )
                    target.save(update_fields=["is_club_admin", "is_game_master"])
            except _LastAdmin as exc:
                return render_modal_or_page(
                    request,
                    "accounts/people/_roles_modal.html",
                    "accounts/people/roles.html",
                    {
                        "form": form,
                        "membership": membership,
                        "who": who,
                        "error": str(exc),
                    },
                )
            if is_htmx(request):
                return hx_response(
                    trigger={
                        "appModalClose": True,
                        "peopleChanged": True,
                        "toast": {
                            "message": f"Roles updated for {who}.",
                            "type": "success",
                        },
                    }
                )
            messages.success(request, f"Roles updated for {who}.")
            return redirect("accounts:index", club_slug=request.club.slug)
    else:
        form = RolesForm(
            initial={
                "is_club_admin": membership.is_club_admin,
                "is_game_master": membership.is_game_master,
            }
        )
    ctx = {
        "form": form,
        "membership": membership,
        "who": who,
    }
    return render_modal_or_page(
        request,
        "accounts/people/_roles_modal.html",
        "accounts/people/roles.html",
        ctx,
    )
