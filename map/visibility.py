from urllib.parse import urlencode

from accounts.permissions import is_club_admin, is_game_master
from player_characters.models import Character

from .models import FoundMark, Location, LocationCredit, TileVisit


def is_map_editor(user, club):
    return is_club_admin(user, club) or is_game_master(user, club)


def own_characters(request):
    membership = getattr(request, "membership", None)
    if membership is None:
        return Character.objects.none()
    return Character.objects.for_club(request.club).filter(owner=membership)


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
    wants_players = request.GET.get("view") == "players"
    explicit = []
    if is_editor and not wants_players:
        players_view = False
        picked = []
        visible = None
    elif is_editor:
        players_view = True
        explicit = list(pick_characters(request, ids, allow_any=True))
        picked = explicit
        visible = visible_positions(hex_map, picked)
    else:
        players_view = True
        explicit = list(pick_characters(request, ids, allow_any=False))
        picked = explicit or list(own_characters(request))
        visible = visible_positions(hex_map, picked)
    if is_editor:
        choices = Character.objects.for_club(request.club).order_by("name")
    else:
        choices = own_characters(request).order_by("name")
    pairs = [("characters", c.pk) for c in explicit]
    if is_editor and players_view:
        pairs.append(("view", "players"))
    return {
        "is_editor": is_editor,
        "players_view": players_view,
        "show_gm": is_editor and not players_view,
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
