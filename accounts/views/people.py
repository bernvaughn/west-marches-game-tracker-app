from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_http_methods

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
    if temp is None:
        messages.success(request, f"{email} already had an account; added to this club.")
        return redirect("accounts:whitelist", club_slug=request.club.slug)
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
                    target.is_club_admin = form.cleaned_data["is_club_admin"]
                    target.is_game_master = form.cleaned_data["is_game_master"]
                    admins = sum(1 for m in memberships if m.is_club_admin)
                    if not target.is_club_admin and admins == 0:
                        raise _LastAdmin(
                            "This club needs at least one club admin. "
                            "Make someone else a club admin first."
                        )
                    target.save(update_fields=["is_club_admin", "is_game_master"])
            except _LastAdmin as exc:
                form.add_error(None, str(exc))
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
