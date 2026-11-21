"""Views for character death and undo actions."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.htmx import htmx_or_redirect, is_htmx
from accounts.permissions import can_see_gm_details, club_member_required
from accounts.scoping import club_get_object_or_404

from ..access import owns_character
from ..character_death_forms import DeathForm
from ..death_permissions import can_mark_dead, can_undo_death
from ..life import LifeError, mark_dead, undo_death
from ..models import Character


@club_member_required
def death(request, club_slug, pk):
    """Mark a character as dead (GET shows modal, POST processes form)."""
    character = club_get_object_or_404(request, Character, pk=pk)

    # Permission check
    if not can_mark_dead(request.user, character):
        raise PermissionDenied

    sheet_url = redirect("characters:detail", club_slug=club_slug, pk=character.pk).url

    # Already dead - refuse with message
    if character.is_dead:
        if request.method == "POST":
            messages.error(request, f"{character.name} is already dead.")
            return htmx_or_redirect(request, sheet_url)
        # For HTMX GET, show modal with error
        if is_htmx(request):
            form = DeathForm({})
            form.add_error(None, f"{character.name} is already dead.")
            return render(
                request,
                "player_characters/characters/_death_modal.html",
                {"character": character, "form": form},
            )
        # Non-HTMX GET redirects to sheet
        messages.error(request, f"{character.name} is already dead.")
        return redirect(sheet_url)

    if request.method == "POST":
        form = DeathForm(request.POST)
        if form.is_valid():
            try:
                mark_dead(
                    character,
                    by=request.membership,
                    died_on=form.cleaned_data["died_on"],
                    note=form.cleaned_data["note"],
                )
            except LifeError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"{character.name} is marked as dead.")
                return htmx_or_redirect(request, sheet_url)

        # Form invalid - re-render modal for HTMX, redirect for non-HTMX
        if is_htmx(request):
            return render(
                request,
                "player_characters/characters/_death_modal.html",
                {"character": character, "form": form},
            )
        messages.error(request, "Invalid form data.")
        return redirect(sheet_url)

    # GET - show modal for HTMX, redirect for non-HTMX
    form = DeathForm()
    if is_htmx(request):
        return render(
            request,
            "player_characters/characters/_death_modal.html",
            {"character": character, "form": form},
        )
    return redirect(sheet_url)


@club_member_required
@require_POST
def death_undo(request, club_slug, pk):
    """Undo a character's death (POST only)."""
    character = club_get_object_or_404(request, Character, pk=pk)

    # Basic permission: owner, GM, club admin, or site admin
    user = request.user
    is_owner = owns_character(user, character)
    is_gm_or_admin = can_see_gm_details(user, character.club)
    if not (user.is_superuser or is_owner or is_gm_or_admin):
        raise PermissionDenied

    # If character is not dead, allow through to undo_death which will raise LifeError
    # If character is dead, enforce the 24h/own-mark rules via can_undo_death
    if character.is_dead and not can_undo_death(user, character):
        raise PermissionDenied

    sheet_url = redirect("characters:detail", club_slug=club_slug, pk=character.pk).url

    try:
        undo_death(character, by=request.membership)
    except LifeError as exc:
        messages.error(request, str(exc))
        return htmx_or_redirect(request, sheet_url)

    messages.success(request, f"{character.name} is back in play.")
    return htmx_or_redirect(request, sheet_url)
