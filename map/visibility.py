from urllib.parse import urlencode

from accounts.permissions import is_club_admin, is_game_master
from player_characters.models import Character
from player_characters.selection import own_characters as _own_characters
from player_characters.selection import selected_character

from .models import FoundMark, Location, LocationCredit, TileVisit


def is_map_editor(user, club):
    return is_club_admin(user, club) or is_game_master(user, club)


def own_characters(request):
    return _own_characters(request)


def pick_characters(request, ids, allow_any):
    parsed = []
    for value in ids:
        try:
            parsed.append(int(value))
        except (TypeError, ValueError):
            continue
    base = Character.objects.for_club(request.club) if allow_any else own_characters(request)
    return base.filter(pk__in=parsed)


def visible_positions(hex_map, characters):
    positions = set(
        TileVisit.objects.filter(map=hex_map, character__in=characters).values_list("q", "r")
    )
    positions.add((0, 0))
    return positions


def resolve_view(request, hex_map):
    """One place for the M8 and M10 rules. Returns the view state for a request."""
    is_editor = is_map_editor(request.user, request.club)
    ids = request.GET.getlist("characters")
    wanted = request.GET.get("view")
    has_own = own_characters(request).exists()
    can_pick_own = is_editor and has_own
    if not is_editor or (wanted == "mine" and can_pick_own):
        mode = "mine"
    elif wanted == "players":
        mode = "players"
    else:
        mode = "full"
    explicit = []
    if mode == "full":
        picked = []
        visible = None
    elif mode == "players":
        explicit = list(pick_characters(request, ids, allow_any=True))
        picked = explicit
        visible = visible_positions(hex_map, picked)
    else:
        explicit = list(pick_characters(request, ids, allow_any=False))
        sel = selected_character(request)
        picked = explicit or ([sel] if sel else [])
        visible = visible_positions(hex_map, picked)
    players_view = mode != "full"
    if mode == "players":
        choices = Character.objects.for_club(request.club).order_by("name")
    else:
        choices = own_characters(request).order_by("name")
    view_param = mode if is_editor and mode != "full" else ""
    pairs = [("characters", c.pk) for c in explicit]
    if view_param:
        pairs.append(("view", view_param))
    return {
        "is_editor": is_editor,
        "players_view": players_view,
        "show_gm": mode == "full",
        "view_param": view_param,
        "can_pick_own": can_pick_own,
        "picked": picked,
        "picked_ids": {c.pk for c in picked},
        "choices": list(choices),
        "visible": visible,
        "char_params": urlencode(pairs),
    }


def found_location_ids(characters):
    """Ids of locations these characters found: credit of either kind, or a found mark."""
    characters = list(characters)
    if not characters:
        return set()
    credited = LocationCredit.objects.filter(characters__in=characters).values_list(
        "location_id", flat=True
    )
    marked = FoundMark.objects.filter(character__in=characters).values_list(
        "location_id", flat=True
    )
    return set(credited) | set(marked)


def placeholder_location_ids(hex_map, visible_positions, found_ids):
    """Ids of discovered but not found locations on visible tiles."""
    discovered = set(
        LocationCredit.objects.filter(
            location__tile__map=hex_map,
            kind=LocationCredit.Kind.DISCOVERED,
            characters__isnull=False,
        ).values_list("location_id", flat=True)
    )
    discovered -= set(found_ids)
    if not discovered:
        return set()
    return {
        pk
        for pk, q, r in Location.objects.filter(pk__in=discovered).values_list(
            "pk", "tile__q", "tile__r"
        )
        if (q, r) in visible_positions
    }


def location_reveal(hex_map, view):
    """What a player view may show. None means the editors' full view."""
    visible = view["visible"]
    if visible is None:
        return None
    found = found_location_ids(view["picked"])
    on_visible = {
        pk
        for pk, q, r in Location.objects.filter(tile__map=hex_map).values_list(
            "pk", "tile__q", "tile__r"
        )
        if (q, r) in visible
    }
    return {
        "found": found & on_visible,
        "placeholders": placeholder_location_ids(hex_map, visible, found),
    }
