from urllib.parse import urlencode

from accounts.permissions import is_club_admin, is_game_master
from player_characters.models import Character

from .models import TileVisit


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
