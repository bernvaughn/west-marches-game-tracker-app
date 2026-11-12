from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404, club_queryset

from ..hexgrid import pan_links, parse_window
from ..models import HexMap, Tile
from ..render import build_cells
from ..visibility import is_map_editor, location_reveal, resolve_view


def _map_context(request, hex_map, q, r, view, tile=None):
    return {
        "club": request.club,
        "hex_map": hex_map,
        "q": q,
        "r": r,
        "tile": tile,
        "is_editor": view["is_editor"],
        "show_gm": view["show_gm"],
        "players_view": view["players_view"],
        "picked": view["picked"],
        "picked_ids": view["picked_ids"],
        "choices": view["choices"],
        "char_params": view["char_params"],
    }


def _get_map(request, map_id, is_editor):
    hex_map = club_get_object_or_404(request, HexMap, pk=map_id)
    if hex_map.archived and not is_editor:
        raise Http404
    return hex_map


def with_params(url, *queries):
    """Join a url with query strings that have no leading separator."""
    query = "&".join(item for item in queries if item)
    return f"{url}?{query}" if query else url


def location_rows(tile_obj):
    """Locations of a tile with discovered, explored and unexplored set."""
    locations = list(tile_obj.locations.all()) if tile_obj else []
    for loc in locations:
        loc.discovered, loc.explored = [], []
        for credit in loc.credits.all():
            if credit.kind == "discovered":
                loc.discovered = list(credit.characters.all())
            elif credit.kind == "explored":
                loc.explored = list(credit.characters.all())
        loc.unexplored = not loc.explored
    return locations


@club_member_required
def index(request, club_slug):
    is_editor = is_map_editor(request.user, request.club)
    maps = club_queryset(request, HexMap)
    return render(
        request,
        "map/core/index.html",
        {
            "club": request.club,
            "is_editor": is_editor,
            "maps": maps.filter(archived=False),
            "archived": maps.filter(archived=True) if is_editor else [],
        },
    )


@club_member_required
def detail(request, club_slug, map_id):
    is_editor = is_map_editor(request.user, request.club)
    hex_map = _get_map(request, map_id, is_editor)
    cq, cr, radius = parse_window(request.GET)
    view = resolve_view(request, hex_map)
    ctx = _map_context(request, hex_map, cq, cr, view)
    char_params = view["char_params"]
    base = reverse("map:detail", kwargs={"club_slug": club_slug, "map_id": hex_map.pk})
    pan = [
        {
            "name": name,
            "url": with_params(base, urlencode({"q": q, "r": r, "radius": radius}), char_params),
        }
        for name, (q, r) in pan_links(cq, cr, radius).items()
    ]
    window = urlencode({"q": cq, "r": cr, "radius": radius})
    print_base = reverse("map:print", kwargs={"club_slug": club_slug, "map_id": hex_map.pk})
    reveal = location_reveal(hex_map, view)
    ctx.update(
        build_cells(
            hex_map,
            cq,
            cr,
            radius,
            view["visible"],
            char_params,
            club_slug=club_slug,
            reveal=reveal,
        )
    )
    ctx.update(
        pan=pan,
        radius=radius,
        window=window,
        has_characters=bool(view["picked"]),
        print_url=with_params(print_base, window, char_params),
        full_url=with_params(base, window),
        players_url=with_params(base, window, "view=players"),
    )
    return render(request, "map/core/detail.html", ctx)


@club_member_required
def tile(request, club_slug, map_id, q, r):
    is_editor = is_map_editor(request.user, request.club)
    hex_map = _get_map(request, map_id, is_editor)
    view = resolve_view(request, hex_map)
    visible = view["visible"]
    if visible is not None and (q, r) not in visible:
        raise Http404
    tile_obj = (
        Tile.objects.for_club(request.club)
        .filter(map=hex_map, q=q, r=r)
        .prefetch_related("locations__encounters", "locations__credits__characters")
        .first()
    )
    ctx = _map_context(request, hex_map, q, r, view, tile=tile_obj)
    back = reverse("map:detail", kwargs={"club_slug": club_slug, "map_id": hex_map.pk})
    locations = location_rows(tile_obj)
    placeholders = []
    reveal = location_reveal(hex_map, view)
    if reveal is not None:
        placeholders = [
            {"request_id": loc.pk}
            for loc in sorted(locations, key=lambda loc: loc.pk)
            if loc.pk in reveal["placeholders"]
        ]
        locations = [loc for loc in locations if loc.pk in reveal["found"]]
    ctx.update(
        locations=locations,
        placeholders=placeholders,
        back_url=with_params(back, urlencode({"q": q, "r": r}), view["char_params"]),
        players_url=with_params(request.path, "view=players"),
        full_url=request.path,
    )
    return render(request, "map/core/tile.html", ctx)
