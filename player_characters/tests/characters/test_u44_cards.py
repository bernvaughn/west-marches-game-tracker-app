import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

pytestmark = [pytest.mark.story("U44"), pytest.mark.django_db]

HINT = "turn off Headers and footers"


def all_url(club, c):
    return reverse("characters:print_items", args=[club.slug, c.pk])


def one_url(club, c, item, layout):
    return reverse("characters:print_item", args=[club.slug, c.pk, item.pk]) + f"?layout={layout}"


def css(name):
    return (Path(settings.BASE_DIR) / "static" / "css" / name).read_text()


def test_cards_show_symbol_value_footer(login, club, player, funded, item):
    item.symbol = "🪢"
    item.value_cp = 1500
    item.save()
    today = timezone.localdate().strftime("%Y-%m-%d")
    c = login(player)
    for r in (
        c.get(all_url(club, funded)),
        c.get(one_url(club, funded, item, "grid")),
        c.get(one_url(club, funded, item, "full")),
    ):
        body = r.content.decode()
        assert 'wm-item-card-icon" aria-hidden="true">🪢' in body
        assert 'wm-pill-value">15 gp<' in body
        assert f"{funded.name} · printed {today}" in body


def test_zero_value_shown(login, club, player, funded, item):
    item.value_cp = 0
    item.save()
    assert 'wm-pill-value">0 cp<' in login(player).get(all_url(club, funded)).content.decode()


def test_print_css_margin_and_fit():
    p = css("print.css")
    assert re.search(r"@page cards\s*{[^}]*margin:\s*0;", p)
    m = re.search(r"\.wm-card-sheet\s*{[^}]*padding:\s*([\d.]+)in\s+([\d.]+)in", p)
    top, side = float(m.group(1)), float(m.group(2))
    assert 7.5 + 2 * side <= 8.27
    assert 10.5 + 2 * top <= 11


def test_grid_still_3x3():
    c = css("areas/characters.css")
    assert "repeat(3, 2.5in)" in c and "grid-auto-rows: 3.5in" in c


def test_grid_page_cells(login, club, player, funded, item):
    body = login(player).get(one_url(club, funded, item, "grid")).content.decode()
    assert body.count('<article class="wm-item-card wm-pass"') == 1
    assert body.count("wm-card-cell") == 8


def test_hint_on_print_pages(login, club, player, funded, item):
    c = login(player)
    for u in (all_url(club, funded), one_url(club, funded, item, "grid")):
        body = c.get(u).content.decode()
        assert re.search(r'class="no-print[^"]*"[^>]*>[^<]*' + HINT, body)
    choose = reverse("characters:print_item", args=[club.slug, funded.pk, item.pk])
    assert HINT not in c.get(choose).content.decode()


def test_symbol_shows_on_sheet_and_history(login, player, club, funded, item):
    item.symbol = "🪢"
    item.save()
    c = login(player)
    assert (
        '<span class="wm-item-symbol" aria-hidden="true">🪢</span> Rope'
        in c.get(reverse("characters:detail", args=[club.slug, funded.pk])).content.decode()
    )
    assert (
        '<span class="wm-item-symbol" aria-hidden="true">🪢</span> Rope'
        in c.get(reverse("ledger:character_history", args=[club.slug, funded.pk])).content.decode()
    )
