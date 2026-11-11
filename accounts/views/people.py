from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.cache import add_never_cache_headers

from player_characters.models import Character

from ..forms.people import WhitelistForm
from ..models import Membership, WhitelistEntry
from ..passwords import get_or_create_member
from ..permissions import club_admin_required, club_member_required
from ..scoping import club_queryset


@club_member_required
def member_list(request, club_slug):
    members = (
        club_queryset(request, Membership)
        .select_related("user")
        .prefetch_related("characters")
        .order_by("user__display_name", "user__email")
    )
    return render(request, "accounts/people/member_list.html", {"members": members})


def _whitelist_page(request, form, **extra):
    entries = club_queryset(request, WhitelistEntry).order_by("email")
    ctx = {"form": form, "entries": entries, **extra}
    return render(request, "accounts/people/whitelist.html", ctx)


@club_admin_required
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
