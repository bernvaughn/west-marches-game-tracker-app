from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.services import LedgerError, Line, available_items, recent_changes, record

from ..access import owns_character
from ..forms_adjust import PlayerConsumeForm
from ..models import Character


@club_member_required
def player_consume(request, club_slug, pk, item_pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    item = club_get_object_or_404(request, Item, pk=item_pk)
    if not owns_character(request.user, character):
        raise PermissionDenied
    available = available_items(character).get(item.pk, 0)
    if available < 1:
        raise Http404("The character has none of this item available.")
    sheet = redirect("characters:detail", club_slug=club_slug, pk=character.pk)
    if request.method == "POST":
        form = PlayerConsumeForm(request.POST, available=available)
        if form.is_valid():
            quantity = form.cleaned_data["quantity"]
            try:
                record(
                    character,
                    "consumed",
                    [Line(item=item, quantity=-quantity)],
                    note=form.cleaned_data["note"],
                    actor=request.user,
                )
            except LedgerError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"Consumed {quantity} {item.name}.")
                if is_htmx(request):
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = sheet.url
                    return response
                return sheet
    else:
        form = PlayerConsumeForm(available=available)
    return render_modal_or_page(
        request,
        "player_characters/characters/_consume_modal.html",
        "player_characters/characters/player_consume.html",
        {
            "character": character,
            "item": item,
            "available": available,
            "form": form,
            "recent": recent_changes(character),
        },
    )
