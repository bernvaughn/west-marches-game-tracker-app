import pytest

from map.models import HexMap, Tile, XPLevel
from map.xp import DEFAULT_XP_TABLE, copy_default_xp_table

pytestmark = pytest.mark.story("FOUNDATION")


def test_new_map_has_safe_town(club):
    m = HexMap.objects.create(club=club, name="West")
    tile = m.tiles.get()
    assert (tile.q, tile.r, tile.is_safe_town) == (0, 0, True)
    m.name = "West 2"
    m.save()
    assert Tile.objects.filter(map=m).count() == 1


def test_copy_xp_table_exact_and_idempotent(club):
    copy_default_xp_table(club)
    copy_default_xp_table(club)
    rows = list(XPLevel.objects.filter(club=club))
    assert len(rows) == 10
    got = {r.band: (r.discover_xp, r.explore_xp) for r in rows}
    assert got == {b: (d, e) for b, d, e in DEFAULT_XP_TABLE}
    assert got["5-6"] == (2825, 8475)
    assert got["19-20"] == (22500, 67500)


def test_copy_xp_table_keeps_edits(club):
    copy_default_xp_table(club)
    XPLevel.objects.filter(club=club, band="1-2").update(discover_xp=1)
    copy_default_xp_table(club)
    assert XPLevel.objects.get(club=club, band="1-2").discover_xp == 1
