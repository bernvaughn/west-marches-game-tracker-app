from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from accounts.htmx import render_modal_or_page
from accounts.mixins import ClubContextMixin, ClubScopedMixin
from accounts.permissions import club_member_required

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
        "view_param": view["view_param"],
        "can_pick_own": view["can_pick_own"],
    }


def _get_map(request_or_view, map_id, is_editor):
    """Get a club-scoped map by ID, raising Http404 if not found or archived."""
    # Handle both class-based views (with mixin) and function-based views (with request)
    if hasattr(request_or_view, "get_club_object_or_404"):
        hex_map = request_or_view.get_club_object_or_404(HexMap, pk=map_id)
    else:
        from accounts.scoping import club_get_object_or_404

        hex_map = club_get_object_or_404(request_or_view, HexMap, pk=map_id)
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


@method_decorator(club_member_required, name="dispatch")
class IndexView(ClubScopedMixin, ClubContextMixin, View):
    def get(self, request, club_slug):
        is_editor = is_map_editor(request.user, self.club)
        maps = self.get_club_queryset(HexMap)
        return render(
            request,
            "map/core/index.html",
            {
                "club": self.club,
                "is_editor": is_editor,
                "maps": maps.filter(archived=False),
                "archived": maps.filter(archived=True) if is_editor else [],
            },
        )


@method_decorator(club_member_required, name="dispatch")
class DetailView(ClubScopedMixin, ClubContextMixin, View):
    def get(self, request, club_slug, map_id):
        is_editor = is_map_editor(request.user, self.club)
        hex_map = _get_map(self, map_id, is_editor)
        cq, cr, radius = parse_window(request.GET)
        view = resolve_view(request, hex_map)
        ctx = _map_context(request, hex_map, cq, cr, view)
        char_params = view["char_params"]
        base = reverse("map:detail", kwargs={"club_slug": club_slug, "map_id": hex_map.pk})
        pan = [
            {
                "name": name,
                "url": with_params(
                    base, urlencode({"q": q, "r": r, "radius": radius}), char_params
                ),
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
            mine_url=with_params(base, window, "view=mine"),
        )
        ctx["tile_modal"] = True
        ctx["fit_screen"] = True
        return render(request, "map/core/detail.html", ctx)


@method_decorator(club_member_required, name="dispatch")
class TileView(ClubScopedMixin, ClubContextMixin, View):
    def get(self, request, club_slug, map_id, q, r):
        is_editor = is_map_editor(request.user, self.club)
        hex_map = _get_map(self, map_id, is_editor)
        view = resolve_view(request, hex_map)
        visible = view["visible"]
        if visible is not None and (q, r) not in visible:
            raise Http404
        tile_obj = (
            Tile.objects.for_club(self.club)
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
            mine_url=with_params(request.path, "view=mine"),
            full_url=request.path,
        )
        ctx["tile_page_url"] = request.get_full_path()
        return render_modal_or_page(request, "map/core/_tile_modal.html", "map/core/tile.html", ctx)
