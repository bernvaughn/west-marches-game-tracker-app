from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..access import require_inventory_access
from ..inventory import coin_summary, inventory_rows
from ..item_cards import CARD_CAP, CARDS_PER_SHEET, build_cards, chunk, too_many
from ..models import Character

LAYOUTS = ("full", "grid")
COPIES = ("type", "item")


@club_member_required
def print_items(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)
    copies = request.GET.get("copies", "type")
    if copies not in COPIES:
        return HttpResponseBadRequest("Unknown copies.")
    pairs = [(r.item, r.owned) for r in inventory_rows(character)]
    over = too_many(pairs, copies)
    sheets = [] if over else chunk(build_cards(pairs, copies))
    return render(
        request,
        "player_characters/characters/print.html",
        {
            "character": character,
            "owner": character.name,
            "sheets": sheets,
            "copies": copies,
            "too_many": over,
            "card_cap": CARD_CAP,
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
    context = {
        "character": character,
        "owner": character.name,
        "row": row,
        "printed_on": timezone.localdate(),
        "card_cap": CARD_CAP,
    }
    if layout is None:
        return render(request, "player_characters/characters/print_item_choose.html", context)
    if layout not in LAYOUTS:
        return HttpResponseBadRequest("Unknown layout.")
    copies = request.GET.get("copies", "type")
    if copies not in COPIES:
        return HttpResponseBadRequest("Unknown copies.")
    pairs = [(row.item, row.owned)]
    over = too_many(pairs, copies)
    cards = [] if over else build_cards(pairs, copies)
    if layout == "full":
        sheets = []
    else:
        sheets = chunk(cards)
        pad = (-len(cards)) % CARDS_PER_SHEET
        context["empty_cells"] = range(pad)
    context.update(layout=layout, copies=copies, too_many=over, cards=cards, sheets=sheets)
    return render(request, "player_characters/characters/print_item.html", context)
