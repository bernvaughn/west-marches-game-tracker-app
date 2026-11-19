from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from quests.services import missing_items, needed_by_open_quests

from ..access import require_inventory_access
from ..inventory import coin_summary, inventory_rows
from ..item_cards import CARD_CAP, CARDS_PER_SHEET, build_cards, chunk, too_many
from ..junk import junk_rows
from ..models import Character
from ..sheet import ability_modifier, ability_rows, passive_perception

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
    row = next(
        (r for r in inventory_rows(character) if r.item.pk == item_pk),
        None,
    )
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
        return render(
            request,
            "player_characters/characters/print_item_choose.html",
            context,
        )
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


@club_member_required
def print_session_pack(request, club_slug, pk):
    """Combined print view for session pack: character sheet, item cards,
    quests, map."""
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)

    # Parse query parameters for print options
    include_sheet = request.GET.get("sheet", "1") == "1"
    include_items = request.GET.get("items", "1") == "1"
    include_quests = request.GET.get("quests", "1") == "1"
    include_map = request.GET.get("map", "0") == "1"

    # Character sheet data
    coins = coin_summary(character)
    inv_rows = inventory_rows(character)
    junk = junk_rows(character)
    junk_val = sum(r.item.value_cp * r.quantity for r in junk)

    # Abilities (using shared sheet helper)
    abilities = ability_rows(character)
    passive_perception_val = passive_perception(ability_modifier(character.wisdom))

    # Item cards data
    pairs = [(r.item, r.owned) for r in inv_rows]
    over = too_many(pairs, "type")
    item_sheets = [] if over else chunk(build_cards(pairs, "type"))

    # Ready quests data (using quests.services)
    ready_quests = []
    if include_quests:
        today = timezone.localdate()
        open_quests_by_item = needed_by_open_quests(character, today)
        # Deduplicate quests since a quest with multiple requirements appears under each item
        seen = set()
        for quests in open_quests_by_item.values():
            for q in quests:
                if q.pk in seen:
                    continue
                seen.add(q.pk)
                if not missing_items(q, character):
                    ready_quests.append(q)

    show_map = include_map

    return render(
        request,
        "player_characters/characters/print_session_pack.html",
        {
            "character": character,
            "owner": character.name,
            "include_sheet": include_sheet,
            "include_items": include_items,
            "include_quests": include_quests,
            "include_map": include_map,
            "coins": coins,
            "inv_rows": inv_rows,
            "junk": junk,
            "junk_value": junk_val,
            "abilities": abilities,
            "passive_perception": passive_perception_val,
            "item_sheets": item_sheets,
            "too_many": over,
            "card_cap": CARD_CAP,
            "ready_quests": ready_quests,
            "show_map": show_map,
            "printed_on": timezone.localdate(),
        },
    )
