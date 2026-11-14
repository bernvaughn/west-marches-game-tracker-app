import re
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError

from .test_sheet import u
from .test_u69_sheet import FULL

CSS = Path(__file__).resolve().parents[3] / "static" / "css"


def _post(c, club, ch, **kw):
    return c.post(u("characters:edit", club, ch.pk), {**FULL, **kw})


@pytest.mark.story("U88")
@pytest.mark.parametrize("val,expected", [("", None), ("1", 1), ("500", 500)])
def test_max_hp_valid(club, login, player, funded, val, expected):
    assert _post(login(player), club, funded, max_hp=val).status_code == 302
    funded.refresh_from_db()
    assert funded.max_hp == expected


@pytest.mark.story("U88")
@pytest.mark.parametrize("val", ["0", "-1"])
def test_max_hp_below_one_refused(club, login, player, funded, val):
    funded.max_hp = 7
    funded.save()
    assert _post(login(player), club, funded, max_hp=val).status_code == 200
    funded.refresh_from_db()
    assert funded.max_hp == 7


@pytest.mark.story("U88")
def test_max_hp_model_refuses_zero(funded):
    funded.max_hp = 0
    with pytest.raises(ValidationError):
        funded.full_clean()


@pytest.mark.story("U88")
@pytest.mark.parametrize("who", ["player", "game_master", "club_admin"])
def test_max_hp_editors(club, login, funded, request, who):
    user = request.getfixturevalue(who)
    assert _post(login(user), club, funded, max_hp="31").status_code == 302
    funded.refresh_from_db()
    assert funded.max_hp == 31


@pytest.mark.story("U88")
def test_max_hp_other_player_refused(club, login, other_player, funded):
    r = _post(login(other_player), club, funded, max_hp="31")
    assert r.status_code in (403, 404)
    funded.refresh_from_db()
    assert funded.max_hp is None


@pytest.mark.story("U88")
def test_max_hp_foreign_club_isolated(club, login, foreign_member, funded):
    c = login(foreign_member)
    assert c.get(u("characters:detail", club, funded.pk)).status_code == 404
    assert _post(c, club, funded, max_hp="9").status_code in (403, 404)
    funded.refresh_from_db()
    assert funded.max_hp is None


@pytest.mark.story("U88")
def test_max_hp_in_combat_box(club, login, player, funded):
    c = login(player)
    html = c.get(u("characters:detail", club, funded.pk)).content.decode()
    assert "Max HP" in html
    funded.max_hp = 42
    funded.save()
    html = c.get(u("characters:detail", club, funded.pk)).content.decode()
    assert re.search(r"<dt>Max HP</dt><dd>42</dd>", html)


@pytest.mark.story("U87")
def test_print_css_hides_interactive_at_end():
    css = (CSS / "print.css").read_text()
    block = css[css.index("U87: nothing interactive prints") :]
    for sel in [
        ".tooltip",
        '[role="tooltip"]',
        "button",
        ".btn",
        "input",
        "select",
        ".dropdown-menu",
        "display: none",
    ]:
        assert sel in block
    assert css.index("Character slips") < css.index("U87: nothing interactive prints")


@pytest.mark.story("U87")
def test_sheet_print_grid_and_text_floor():
    css = (CSS / "areas" / "characters.css").read_text()
    start = css.index("@media print {\n  @page { margin: 12mm; }")
    block = css[start : css.index("/* U59", start)]
    assert re.search(r"\.wm-sheet-layout[^{]*\{[^}]*grid-template-columns: 1fr 1fr", block)
    sizes = [float(x) for x in re.findall(r"font-size: ([\d.]+)pt", block)]
    assert sizes and min(sizes) >= 10


@pytest.mark.story("U87")
def test_sheet_and_print_view_render(club, login, player, funded):
    c = login(player)
    assert c.get(u("characters:detail", club, funded.pk)).status_code == 200
    assert c.get(u("characters:print_items", club, funded.pk)).status_code == 200


@pytest.mark.story("U87")
def test_sheet_print_header_beats_components_rule():
    css = (CSS / "areas" / "characters.css").read_text()
    start = css.index("@media print {\n  @page { margin: 12mm; }")
    block = css[start : css.index("/* U59", start)]
    rule = re.search(r"\.wm-sheet \.wm-sheet-table\.table > thead > tr > th \{([^}]*)\}", block)
    assert rule and "font-size: 10pt" in rule.group(1)
    assert re.search(r"\.wm-sheet \.wm-badge \{[^}]*font-size: 10pt", block)
