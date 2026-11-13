import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from .test_sheet import sheet, u  # noqa: F401

ROOT = Path(settings.BASE_DIR)


def section(html, sid):
    return re.search(rf'<section class="([^"]*)" aria-labelledby="{sid}"', html).group(1)


@pytest.mark.story("U80")
def test_sheet_rows(club, login, player, sheet):  # noqa: F811
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert "wm-sheet-half" in section(html, "sheet-combat")
    assert "wm-sheet-half" in section(html, "sheet-description")
    assert "wm-sheet-full" in section(html, "sheet-items")
    assert html.index("sheet-combat") < html.index("sheet-description") < html.index("sheet-items")
    assert "wm-sheet-inventory" in html


@pytest.mark.story("U80")
def test_css_rules():
    chars = (ROOT / "static/css/areas/characters.css").read_text()
    assert "min-width: 768px" in chars and "overflow-x: visible" in chars
    comp = (ROOT / "static/css/components.css").read_text()
    main = re.search(r"\.wm-main \{([^}]*)\}", comp).group(1)
    assert "margin-inline: auto" in main and "max-width: 72rem" in main


@pytest.mark.story("U80")
def test_full_width_pages(club, login, club_admin):
    c = login(club_admin)
    for name in ("shops:index", "downtime:agenda"):
        html = c.get(reverse(name, args=[club.slug])).content.decode()
        assert "wm-main--full" in html, name
    html = c.get(reverse("characters:directory", args=[club.slug])).content.decode()
    assert "wm-main--full" not in html


@pytest.mark.story("U80")
def test_directory_columns(club, login, player, character):
    html = login(player).get(reverse("characters:directory", args=[club.slug])).content.decode()
    ths = re.findall(r"<th>(.*?)</th>", html)
    assert ths[:4] == ["Name", "Species", "Class", "Level"] and ths[-1] == "Player"
