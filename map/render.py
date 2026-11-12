from django.db.models import Exists, OuterRef, Prefetch
from django.urls import reverse

from .hexgrid import hex_points, to_pixel, window_bounds, window_positions
from .models import Location, LocationCredit, Tile


def build_cells(
    hex_map, cq, cr, radius, visible=None, url_params="", size=30, club_slug=None, reveal=None
):
    club_slug = club_slug or hex_map.club.slug
    q_min, q_max, r_min, r_max = window_bounds(cq, cr, radius)
    tiles = {
        (t.q, t.r): t
        for t in Tile.objects.filter(
            map=hex_map, q__range=(q_min, q_max), r__range=(r_min, r_max)
        ).prefetch_related(
            Prefetch(
                "locations",
                queryset=Location.objects.annotate(
                    is_explored=Exists(
                        LocationCredit.objects.filter(
                            location=OuterRef("pk"), kind=LocationCredit.Kind.EXPLORED
                        )
                    )
                ),
            )
        )
    }
    cells = []
    for q, r in window_positions(cq, cr, radius):
        x, y = to_pixel(q, r, size)
        shown = visible is None or (q, r) in visible
        tile = tiles.get((q, r)) if shown else None
        locations = list(tile.locations.all()) if tile else []
        placeholders = 0
        if reveal is not None:
            placeholders = sum(1 for loc in locations if loc.pk in reveal["placeholders"])
            locations = [loc for loc in locations if loc.pk in reveal["found"]]
        fill = ""
        if tile and (locations or placeholders or tile.is_safe_town):
            fill = (
                tile.color or next((loc.color for loc in locations if loc.color), "") or "lightgrey"
            )
        cells.append(
            {
                "x": round(x, 2),
                "y": round(y, 2),
                "points": hex_points(x, y, size),
                "q": q,
                "r": r,
                "tile": tile,
                "count": len(locations) + placeholders,
                "unknown": placeholders,
                "unexplored": sum(1 for loc in locations if not loc.is_explored),
                "symbol": next((loc.symbol for loc in locations if loc.symbol), ""),
                "fill": fill,
                "visited": visible is not None and shown and not fill,
                "shown": shown,
                "safe": bool(tile and tile.is_safe_town),
                "url": (
                    reverse(
                        "map:tile",
                        kwargs={"club_slug": club_slug, "map_id": hex_map.pk, "q": q, "r": r},
                    )
                    + (f"?{url_params}" if url_params else "")
                    if shown
                    else ""
                ),
            }
        )
    pad = size
    xs = [c["x"] for c in cells]
    ys = [c["y"] for c in cells]
    minx, miny = min(xs) - pad, min(ys) - pad
    viewbox = f"{minx:.2f} {miny:.2f} {max(xs) + pad - minx:.2f} {max(ys) + pad - miny:.2f}"
    return {"cells": cells, "viewbox": viewbox}
