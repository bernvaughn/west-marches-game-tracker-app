"""HTMX modal views for adding, editing and removing player-written items.

Only the character's owner, a game master or a club admin may change
entries. All views follow the ``render_modal_or_page`` pattern used by
the item note editor.
"""

from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse

from accounts.htmx import htmx_or_redirect, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from player_characters.access import require_inventory_access
from player_characters.models import Character

from ..forms import PlayerItemForm
from ..models import PlayerItem
from ..services import add_player_item, edit_player_item, remove_player_item


def _sheet_url(request, character):
    return redirect("characters:detail", club_slug=request.club.slug, pk=character.pk).url


def _load_character_and_item(request, character_pk, pk=None):
    character = club_get_object_or_404(request, Character, pk=character_pk)
    require_inventory_access(request.user, character)
    player_item = None
    if pk is not None:
        player_item = club_get_object_or_404(request, PlayerItem, pk=pk)
        if player_item.character_id != character.pk:
            raise Http404("That item is not on this character's sheet.")
    return character, player_item


@club_member_required
def add_entry(request, club_slug, character_pk):
    """HTMX modal: add a player-written item to a character sheet."""
    character, _ = _load_character_and_item(request, character_pk)
    sheet_url = _sheet_url(request, character)
    action = reverse("player_items:add", args=[request.club.slug, character.pk])
    if request.method == "POST":
        form = PlayerItemForm(request.POST)
        if form.is_valid():
            try:
                add_player_item(
                    request.club,
                    character,
                    form.cleaned_data["name"],
                    form.cleaned_data["quantity"],
                    form.cleaned_data["note"],
                    request.user,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return htmx_or_redirect(request, sheet_url)
    else:
        form = PlayerItemForm()
    return render_modal_or_page(
        request,
        "player_items/_entry_form.html",
        "player_items/_entry_form.html",
        {
            "character": character,
            "form": form,
            "modal_title": "Add player-written item",
            "form_action": action,
            "button_label": "Add",
        },
    )


@club_member_required
def edit_entry(request, club_slug, character_pk, pk):
    """HTMX modal: edit a player-written item on a character sheet."""
    character, player_item = _load_character_and_item(request, character_pk, pk)
    sheet_url = _sheet_url(request, character)
    action = reverse("player_items:edit", args=[request.club.slug, character.pk, player_item.pk])
    if request.method == "POST":
        form = PlayerItemForm(request.POST)
        if form.is_valid():
            try:
                edit_player_item(
                    player_item,
                    form.cleaned_data["name"],
                    form.cleaned_data["quantity"],
                    form.cleaned_data["note"],
                    request.user,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return htmx_or_redirect(request, sheet_url)
    else:
        form = PlayerItemForm(
            initial={
                "name": player_item.name,
                "quantity": player_item.quantity,
                "note": player_item.note,
            }
        )
    return render_modal_or_page(
        request,
        "player_items/_entry_form.html",
        "player_items/_entry_form.html",
        {
            "character": character,
            "player_item": player_item,
            "form": form,
            "modal_title": "Edit player-written item",
            "form_action": action,
            "button_label": "Save",
        },
    )


@club_member_required
def remove_entry(request, club_slug, character_pk, pk):
    """HTMX modal: confirm removal of a player-written item."""
    character, player_item = _load_character_and_item(request, character_pk, pk)
    sheet_url = _sheet_url(request, character)
    action = reverse("player_items:remove", args=[request.club.slug, character.pk, player_item.pk])
    if request.method == "POST":
        remove_player_item(player_item, request.user)
        return htmx_or_redirect(request, sheet_url)
    return render_modal_or_page(
        request,
        "player_items/_remove_confirm.html",
        "player_items/_remove_confirm.html",
        {
            "character": character,
            "player_item": player_item,
            "form_action": action,
        },
    )
