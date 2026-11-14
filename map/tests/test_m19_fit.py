import re
from pathlib import Path

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from map.hexgrid import COORD_FONT, MIN_SCALE, fit_svg
from map.render import build_cells

pytestmark = [pytest.mark.story("M19"), pytest.mark.django_db]


def test_fit_large_map_fits_space():
    for w, h in ((1920, 900), (1280, 700)):
        fw, fh, scrolls = fit_svg(800, 600, w, h)
        assert fw <= w + 1e-6 and fh <= h + 1e-6 and not scrolls
        assert abs(fw - w) < 1e-6 or abs(fh - h) < 1e-6
        assert fw / fh == pytest.approx(800 / 600)


def test_fit_respects_minimum():
    fw, fh, scrolls = fit_svg(1000, 900, 390, 600)
    assert (
        scrolls and fw == pytest.approx(1000 * MIN_SCALE) and fh == pytest.approx(900 * MIN_SCALE)
    )


def test_build_cells_min_size(hex_map):
    d = build_cells(hex_map, 0, 0, 15, club_slug="x")
    assert d["min_w"] == pytest.approx(d["vb_w"] * MIN_SCALE, abs=1)
    assert d["min_h"] == pytest.approx(d["vb_h"] * MIN_SCALE, abs=1)


@pytest.mark.parametrize("suffix", ["", "?view=players", "?view=mine"])
def test_coords_shown(club, login, game_master, hex_map, suffix):
    url = reverse("map:detail", args=[club.slug, hex_map.pk]) + suffix
    html = login(game_master).get(url).content.decode()
    assert 'class="hex-coord"' in html
    assert ">1,0<" in html and ">-1,2<" in html
    assert "hexmap--fit" in html


def test_print_not_fit(hex_map):
    html = render_to_string("map/_hexmap.html", build_cells(hex_map, 0, 0, 2, club_slug="x"))
    assert "hexmap--fit" not in html and "min-width" not in html
    assert 'class="hex-coord"' in html


def test_css_rules():
    css = Path("map/static/map/map.css").read_text()
    assert ".hexmap--fit svg { height: auto; min-width: 0 !important" in css
    size = re.search(r"\.hex-coord \{ font-size: (\d+)px", css).group(1)
    assert int(size) == COORD_FONT
