"""Browser-free tests for the pure helpers in scripts/flow_checks/flow_8_map.py."""

from scripts.flow_checks.flow_8_map import (
    DIRECTIONS,
    OPPOSITE,
    TILE_PAGE_RE,
    expected_pan,
    hex_count,
    parse_window_url,
    wait_until,
)


def test_wait_until_returns_value_or_none():
    assert wait_until(lambda: "ok", timeout=1) == "ok"
    assert wait_until(lambda: False, timeout=0.2, interval=0.05) is None


def test_wait_until_swallows_errors_while_polling():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("not yet")
        return True

    assert wait_until(flaky, timeout=2, interval=0.01) is True


def test_hex_count_matches_the_window_size():
    assert hex_count(1) == 7
    assert hex_count(2) == 19
    assert hex_count(6) == 127
    assert hex_count(15) == 721


def test_parse_window_url_uses_app_defaults():
    assert parse_window_url("http://x/c/demo/map/1/") == (0, 0, 6)
    assert parse_window_url("http://x/c/demo/map/1/?q=6&r=-6&radius=6") == (6, -6, 6)
    assert parse_window_url("http://x/c/demo/map/1/?radius=2") == (0, 0, 2)
    assert parse_window_url("http://x/c/demo/map/1/?q=bad") == (0, 0, 6)


def test_expected_pan_moves_by_radius():
    assert expected_pan("E", 0, 0, 6) == (6, 0)
    assert expected_pan("NE", 0, 0, 6) == (6, -6)
    assert expected_pan("SW", 1, 1, 2) == (-1, 3)


def test_opposite_directions_cancel_out():
    for name, back in OPPOSITE.items():
        dq, dr = DIRECTIONS[name]
        bq, br = DIRECTIONS[back]
        assert (dq + bq, dr + br) == (0, 0)
        assert OPPOSITE[back] == name


def test_tile_page_regex():
    assert TILE_PAGE_RE.search("/c/demo/map/1/tile/0/-2/")
    assert TILE_PAGE_RE.search("/c/demo/map/12/tile/-5/10/")
    assert not TILE_PAGE_RE.search("/c/demo/map/1/tile/0/-2")
    assert not TILE_PAGE_RE.search("/c/demo/map/1/")
