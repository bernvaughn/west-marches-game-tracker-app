"""Item note editor (U122): a player's private note on one inventory item.

Only the character's owner may open or submit this form. Game masters, club
admins and site admins read the note on the character sheet but cannot edit it.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect

from accounts.htmx import htmx_or_redirect, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.services import item_quantities

from ..access import owns_character, require_inventory_access
from ..forms_notes import NoteForm
from ..models import Character
from ..notes import NoteError, item_notes, set_note


@club_member_required
def note(request, club_slug, pk, item_pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    item = club_get_object_or_404(request, Item, pk=item_pk)
    require_inventory_access(request.user, character)
    if not owns_character(request.user, character):
        raise PermissionDenied
    owned = item_quantities(character).get(item.pk, 0)
    if owned < 1:
        raise Http404("The character owns none of this item.")
    sheet = redirect("characters:detail", club_slug=club_slug, pk=character.pk)
    sheet_url = sheet.url
    if request.method == "POST":
        form = NoteForm(request.POST)
        if form.is_valid():
            try:
                result = set_note(character, item, form.cleaned_data["text"], request.user)
            except NoteError as exc:
                form.add_error(None, str(exc))
            else:
                if result is None:
                    messages.success(request, f"Cleared note for {item}.")
                else:
                    messages.success(request, f"Saved note for {item}.")
                return htmx_or_redirect(request, sheet_url)
    else:
        form = NoteForm(initial={"text": item_notes(character).get(item.pk, "")})
    return render_modal_or_page(
        request,
        "player_characters/characters/_note_modal.html",
        "player_characters/characters/note.html",
        {"character": character, "item": item, "form": form},
    )
