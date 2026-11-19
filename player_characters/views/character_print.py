from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from map.hexgrid import DEFAULT_RADIUS
from map.models import HexMap
from map.render import build_cells
from map.visibility import location_reveal, visible_positions
from quests.services import missing_items, needed_by_open_quests

from ..access import require_inventory_access
from ..inventory import coin_summary, inventory_rows
from ..item_cards import CARD_CAP, CARDS_PER_SHEET, build_cards, chunk, too_many
from ..junk import junk_rows
from ..models import Character
from ..sheet import ability_modifier, ability_rows, passive_perception

LAYOUTS = ("full", "grid")
COPIES = ("type", "item")

# Session pack options and their defaults for a plain GET link.
PACK_OPTIONS = {"sheet": "1", "items": "1", "quests": "1", "map": "0"}


def pack_options(request):
    """Read the session pack options.

    A POST from the options form carries a "pack" marker. Its checkboxes are
    absent when unchecked, so a missing option means off. Any other request
    reads the query string and falls back to the defaults.
    """
    if request.method == "POST" and "pack" in request.POST:
        return {key: request.POST.get(key) == "1" for key in PACK_OPTIONS}
    return {key: request.GET.get(key, default) == "1" for key, default in PACK_OPTIONS.items()}


def character_maps(request, character):
    """The club's active maps, each as this character's players' view."""
    maps = []
    for hex_map in HexMap.objects.for_club(request.club).filter(archived=False):
        visible = visible_positions(hex_map, [character])
        reveal = location_reveal(hex_map, {"visible": visible, "picked": [character]})
        cells = build_cells(
            hex_map, 0, 0, DEFAULT_RADIUS, visible, club_slug=request.club.slug, reveal=reveal
        )
        maps.append({"hex_map": hex_map, **cells})
    return maps


@club_member_required
def print_items(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)

    # Handle POST: update last_printed_at when user clicks Print
    if request.method == "POST":
        character.last_printed_at = timezone.now()
        character.save(update_fields=["last_printed_at"])

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

    # Handle POST: update last_printed_at when user clicks Print
    if request.method == "POST":
        character.last_printed_at = timezone.now()
        character.save(update_fields=["last_printed_at"])

    options = pack_options(request)
    include_sheet = options["sheet"]
    include_items = options["items"]
    include_quests = options["quests"]
    include_map = options["map"]

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

    maps = character_maps(request, character) if include_map else []

    # Check if request is from htmx (modal flow)
    from_htmx = request.headers.get("HX-Request") == "true"

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
            "maps": maps,
            "printed_on": timezone.localdate(),
            "from_htmx": from_htmx,
        },
    )
