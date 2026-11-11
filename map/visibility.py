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
