from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404, club_queryset

from ..hexgrid import pan_links, parse_window
from ..models import HexMap, Tile
from ..render import build_cells
from ..visibility import is_map_editor, own_characters, visible_positions


def _map_context(request, hex_map, q, r, tile=None, picked=None, char_params=""):
    return {
        "club": request.club,
        "hex_map": hex_map,
        "q": q,
        "r": r,
        "tile": tile,
        "is_editor": is_map_editor(request.user, request.club),
        "picked": picked,
        "char_params": char_params,
    }


def _get_map(request, map_id, is_editor):
    hex_map = club_get_object_or_404(request, HexMap, pk=map_id)
    if hex_map.archived and not is_editor:
        raise Http404
    return hex_map


def _visibility(request, hex_map, is_editor):
    if is_editor:
        return None, None
    picked = list(own_characters(request))
    return picked, visible_positions(hex_map, picked)


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
    picked, visible = _visibility(request, hex_map, is_editor)
    ctx = _map_context(request, hex_map, cq, cr, picked=picked)
    base = reverse("map:detail", kwargs={"club_slug": club_slug, "map_id": hex_map.pk})
    extra = ctx["char_params"]
    pan = [
        {
            "name": name,
            "url": f"{base}?{urlencode({'q': q, 'r': r, 'radius': radius})}{extra}",
        }
        for name, (q, r) in pan_links(cq, cr, radius).items()
    ]
    ctx.update(
        build_cells(hex_map, cq, cr, radius, visible, ctx["char_params"], club_slug=club_slug)
    )
    ctx.update(pan=pan, radius=radius, has_characters=bool(picked))
    return render(request, "map/core/detail.html", ctx)


@club_member_required
def tile(request, club_slug, map_id, q, r):
    is_editor = is_map_editor(request.user, request.club)
    hex_map = _get_map(request, map_id, is_editor)
    picked, visible = _visibility(request, hex_map, is_editor)
    if visible is not None and (q, r) not in visible:
        raise Http404
    tile_obj = (
        Tile.objects.for_club(request.club)
        .filter(map=hex_map, q=q, r=r)
        .prefetch_related("locations__encounters", "locations__credits__characters")
        .first()
    )
    locations = list(tile_obj.locations.all()) if tile_obj else []
    for loc in locations:
        loc.discovered, loc.explored = [], []
        for credit in loc.credits.all():
            if credit.kind == "discovered":
                loc.discovered = list(credit.characters.all())
            elif credit.kind == "explored":
                loc.explored = list(credit.characters.all())
    ctx = _map_context(request, hex_map, q, r, tile=tile_obj, picked=picked)
    back = reverse("map:detail", kwargs={"club_slug": club_slug, "map_id": hex_map.pk})
    ctx.update(
        locations=locations, back_url=f"{back}?{urlencode({'q': q, 'r': r})}{ctx['char_params']}"
    )
    return render(request, "map/core/tile.html", ctx)
