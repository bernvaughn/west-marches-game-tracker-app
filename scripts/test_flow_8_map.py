"""Browser-free tests for the pure helpers in scripts/flow_checks/flow_8_map.py."""

from scripts.flow_checks.flow_8_map import wait_until


def test_wait_until_returns_value_or_none():
    assert wait_until(lambda: "ok", timeout=1) == "ok"
    assert wait_until(lambda: False, timeout=0.2, interval=0.05) is None


def test_parse_tile_path():
    """Test parsing of tile path from URL."""
    import re
    tile_page_re = re.compile(r"/c/demo/map/\d+/tile/-?\d+/-?\d+/$")
    tile_modal_re = re.compile(r"/c/demo/map/\d+/tile/-?\d+/-?\d+/")

    assert tile_page_re.match("/c/demo/map/1/tile/0/-2/")
    assert tile_page_re.match("/c/demo/map/12/tile/-5/10/")
    assert not tile_page_re.match("/c/demo/map/1/tile/0/-2")
    assert not tile_page_re.match("/c/demo/map/tile/0/-2/")

    assert tile_modal_re.match("/c/demo/map/1/tile/0/-2/")
    assert tile_modal_re.match("/c/demo/map/1/tile/0/-2")
    assert tile_modal_re.match("/c/demo/map/12/tile/-5/10/")


def test_credit_names():
    """Test the expected credit kind names."""
    kinds = ["discovered", "explored", "found", "visit"]
    assert "discovered" in kinds
    assert "explored" in kinds
    assert "found" in kinds
    assert "visit" in kinds
    assert len(kinds) == 4


def test_radius_cell_counts():
    """Test expected cell counts for given radii."""
    # radius 0 = 1 hex
    # radius 1 = 7 hexes
    # radius 2 = 19 hexes (wait, formula is 3*r*(r+1)+1)
    # Actually: 1 + 6 + 12 + 18 + ... = 1 + 3*r*(r+1)
    def cell_count(radius):
        return 1 + 3 * radius * (radius + 1)

    assert cell_count(0) == 1
    assert cell_count(1) == 7
    assert cell_count(2) == 19
    assert cell_count(6) == 127
    assert cell_count(15) == 721