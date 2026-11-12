from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..access import require_inventory_access
from ..inventory import coin_summary, inventory_rows
from ..models import Character

CARDS_PER_SHEET = 9
LAYOUTS = ("full", "grid")


@club_member_required
def print_items(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)
    rows = inventory_rows(character)
    sheets = [rows[i : i + CARDS_PER_SHEET] for i in range(0, len(rows), CARDS_PER_SHEET)]
    return render(
        request,
        "player_characters/characters/print.html",
        {
            "character": character,
            "sheets": sheets,
            "coins": coin_summary(character),
            "printed_on": timezone.localdate(),
        },
    )


@club_member_required
def print_item(request, club_slug, pk, item_pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)
    row = next((r for r in inventory_rows(character) if r.item.pk == item_pk), None)
    if row is None:
        raise Http404
    layout = request.GET.get("layout")
    context = {"character": character, "row": row, "printed_on": timezone.localdate()}
    if layout is None:
        return render(request, "player_characters/characters/print_item_choose.html", context)
    if layout not in LAYOUTS:
        return HttpResponseBadRequest("Unknown layout.")
    context.update(layout=layout, empty_cells=range(CARDS_PER_SHEET - 1))
    return render(request, "player_characters/characters/print_item.html", context)
