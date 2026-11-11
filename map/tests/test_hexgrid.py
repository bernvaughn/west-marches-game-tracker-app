import pytest

from map.hexgrid import distance, hex_points, pan_links, parse_window, to_pixel, window_positions

pytestmark = pytest.mark.story("M2")


def test_distance():
    assert distance(0, 0, 0, 0) == 0
    assert distance(0, 0, 1, 0) == 1
    assert distance(0, 0, 1, -1) == 1
    assert distance(0, 0, 2, -1) == 2
    assert distance(0, 0, 1, 1) == 2


@pytest.mark.parametrize("radius", [1, 3, 6, 15])
def test_window_size(radius):
    assert len(window_positions(0, 0, radius)) == 1 + 3 * radius * (radius + 1)


def test_window_large_coordinates():
    positions = window_positions(1000, -1000, 2)
    assert (1000, -1000) in positions
    assert all(distance(1000, -1000, q, r) <= 2 for q, r in positions)


def test_parse_window_defaults_and_bad_values():
    assert parse_window({}) == (0, 0, 6)
    assert parse_window({"q": "x", "r": "", "radius": "y"}) == (0, 0, 6)
    assert parse_window({"q": "-3", "r": "4", "radius": "2"}) == (-3, 4, 2)


def test_parse_window_clamps_radius():
    assert parse_window({"radius": "0"})[2] == 1
    assert parse_window({"radius": "-5"})[2] == 1
    assert parse_window({"radius": "99"})[2] == 15


def test_pan_links():
    links = pan_links(1000, -1000, 6)
    assert links["E"] == (1006, -1000)
    assert links["NW"] == (1000, -1006)
    assert links["SW"] == (994, -994)
    assert len(links) == 6


def test_pixel_and_points():
    assert to_pixel(0, 0, 30) == (0, 0)
    x, y = to_pixel(0, 1, 30)
    assert y == 45
    assert len(hex_points(x, y, 30).split()) == 6
