"""Views for archiving and unarchiving characters (U144)."""

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from accounts.htmx import htmx_or_redirect, render_modal_or_page
from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_get_object_or_404

from ..access import owns_character
from ..life import LifeError, archive, unarchive
from ..models import Character


@club_member_required
def archive(request, club_slug, pk):
    """Archive a character."""
    character = club_get_object_or_404(request, Character, pk=pk)
    _require_can_manage(request, character)

    class ArchiveNoteForm(forms.Form):
        note = forms.CharField(
            required=False,
            max_length=500,
            widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional note"}),
            label="Note",
        )

    if request.method == "POST":
        form = ArchiveNoteForm(request.POST)
        if form.is_valid():
            try:
                archive(character, by=request.membership, note=form.cleaned_data["note"])
            except LifeError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"{character.name} was archived. Their stall is closed.")
                return htmx_or_redirect(request, "characters:detail", club_slug=club_slug, pk=character.pk)
    else:
        form = ArchiveNoteForm()

    ctx = {"character": character, "mode": "archive", "form": form}
    return render_modal_or_page(
        request,
        "player_characters/characters/_archive_modal.html",
        "player_characters/characters/archive.html",
        ctx,
    )


@club_member_required
def unarchive(request, club_slug, pk):
    """Unarchive a character."""
    character = club_get_object_or_404(request, Character, pk=pk)
    _require_can_manage(request, character)

    class ArchiveNoteForm(forms.Form):
        note = forms.CharField(
            required=False,
            max_length=500,
            widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional note"}),
            label="Note",
        )

    if request.method == "POST":
        form = ArchiveNoteForm(request.POST)
        if form.is_valid():
            try:
                unarchive(character, by=request.membership, note=form.cleaned_data["note"])
            except LifeError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"{character.name} was unarchived. Their stall stays closed.")
                return htmx_or_redirect(request, "characters:detail", club_slug=club_slug, pk=character.pk)
    else:
        form = ArchiveNoteForm()

    ctx = {"character": character, "mode": "unarchive", "form": form}
    return render_modal_or_page(
        request,
        "player_characters/characters/_archive_modal.html",
        "player_characters/characters/archive.html",
        ctx,
    )


def _require_can_manage(request, character):
    """Raise PermissionDenied unless the user can manage this character."""
    user = request.user
    club = request.club
    if user.is_superuser:
        return
    if owns_character(user, character):
        return
    if is_game_master(user, club):
        return
    if is_club_admin(user, club):
        return
    raise PermissionDenied