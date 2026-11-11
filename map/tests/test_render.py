import pytest

from map.models import Location, Tile
from map.render import build_cells

pytestmark = pytest.mark.story("M2")


def _cell(data, q, r):
    return next(c for c in data["cells"] if (c["q"], c["r"]) == (q, r))


def test_blank_empty_cells(hex_map):
    data = build_cells(hex_map, 0, 0, 2, club_slug="x")
    empty = _cell(data, 1, 1)
    assert empty["fill"] == "" and empty["count"] == 0 and empty["url"]
    assert 'class="hex hex-empty"' in __import__("django").template.loader.render_to_string(
        "map/_hexmap.html", data
    )


def test_fill_symbol_count(hex_map, tile_location):
    Location.objects.create(tile=tile_location.tile, name="Second", color="blue", symbol="S")
    cell = _cell(build_cells(hex_map, 0, 0, 2, club_slug="x"), 1, 0)
    assert cell["fill"] == "red" and cell["symbol"] == "T" and cell["count"] == 2


def test_tile_colour_wins_and_default_fill(hex_map, tile_location):
    Tile.objects.filter(pk=tile_location.tile.pk).update(color="green")
    assert _cell(build_cells(hex_map, 0, 0, 2, club_slug="x"), 1, 0)["fill"] == "green"
    assert _cell(build_cells(hex_map, 0, 0, 2, club_slug="x"), 0, 0)["fill"] == "lightgrey"


def test_visible_filter(hex_map, tile_location):
    data = build_cells(hex_map, 0, 0, 2, visible={(0, 0), (0, 1)}, club_slug="x")
    assert _cell(data, 1, 0)["url"] == ""
    assert _cell(data, 1, 0)["count"] == 0
    assert _cell(data, 0, 1)["visited"] is True
    assert _cell(data, 0, 1)["url"]


def test_query_count(hex_map, tile_location, django_assert_num_queries):
    with django_assert_num_queries(2):
        build_cells(hex_map, 0, 0, 6, club_slug="x")


def test_large_coordinates(hex_map):
    data = build_cells(hex_map, 1000, -1000, 3, club_slug="x")
    assert len(data["cells"]) == 37
    assert all(c["tile"] is None for c in data["cells"])
