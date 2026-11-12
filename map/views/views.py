from django.shortcuts import render

from accounts.permissions import club_member_required

from ..hexgrid import parse_window, window_positions
from ..models import Location
from ..render import build_cells
from ..visibility import is_map_editor, location_reveal, resolve_view
from .core import _get_map


def _key_rows(request, hex_map, cq, cr, radius, visible, reveal=None):
    positions = set(window_positions(cq, cr, radius))
    qs = (
        Location.objects.for_club(request.club)
        .filter(tile__map=hex_map)
        .select_related("tile")
        .prefetch_related("encounters", "credits__characters")
    )
    rows = []
    unknown = []
    for loc in qs:
        pos = (loc.tile.q, loc.tile.r)
        if pos not in positions or (visible is not None and pos not in visible):
            continue
        if reveal is not None and loc.pk not in reveal["found"]:
            if loc.pk in reveal["placeholders"]:
                unknown.append(pos)
            continue
        loc.discovered, loc.explored = [], []
        for credit in loc.credits.all():
            if credit.kind == "discovered":
                loc.discovered = list(credit.characters.all())
            elif credit.kind == "explored":
                loc.explored = list(credit.characters.all())
        loc.unexplored = not loc.explored
        loc.q, loc.r = pos
        rows.append(loc)
    rows.sort(key=lambda loc: (loc.r, loc.q, loc.name))
    return rows, sorted(unknown, key=lambda p: (p[1], p[0]))


@club_member_required
def print_map(request, club_slug, map_id):
    hex_map = _get_map(request, map_id, is_map_editor(request.user, request.club))
    cq, cr, radius = parse_window(request.GET)
    view = resolve_view(request, hex_map)
    reveal = location_reveal(hex_map, view)
    rows, unknown_rows = _key_rows(request, hex_map, cq, cr, radius, view["visible"], reveal)
    ctx = {
        "club": request.club,
        "hex_map": hex_map,
        "show_gm": view["show_gm"],
        "players_view": view["players_view"],
        "picked": view["picked"],
        "back_params": request.GET.urlencode(),
        "rows": rows,
        "unknown_rows": unknown_rows,
    }
    ctx.update(
        build_cells(
            hex_map,
            cq,
            cr,
            radius,
            view["visible"],
            view["char_params"],
            club_slug=club_slug,
            reveal=reveal,
        )
    )
    return render(request, "map/views/print.html", ctx)
