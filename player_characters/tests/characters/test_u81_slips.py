import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from player_characters.models import Character

pytestmark = [pytest.mark.story("U81"), pytest.mark.django_db]


def printurl(club, chars, extra=""):
    q = "&".join(f"characters={c.pk}" for c in chars)
    return reverse("characters:slips_print", args=[club.slug]) + "?" + q + extra


def sheet(club, c):
    return reverse("characters:detail", args=[club.slug, c.pk])


def slips(club):
    return reverse("characters:slips", args=[club.slug])


def test_twelve_per_page(login, club, game_master, character):
    chars = [character] + [
        Character.objects.create(club=club, owner=character.owner, name=f"Extra {i}")
        for i in range(12)
    ]
    body = login(game_master).get(printurl(club, chars[:12])).content.decode()
    assert body.count('<section class="wm-slip-sheet">') == 1
    assert body.count('<article class="wm-slip">') == 12
    assert body.count("wm-slip-mark") == 12
    body = login(game_master).get(printurl(club, chars)).content.decode()
    sheets = body.split('<section class="wm-slip-sheet">')[1:]
    assert [s.count('<article class="wm-slip">') for s in sheets] == [12, 1]
    css = (Path(settings.BASE_DIR) / "static/css/areas/characters.css").read_text()
    assert "repeat(2, 3.9in)" in css and "grid-auto-rows: 1.7in" in css
    assert re.search(r"\.wm-slip::before\s*{[^}]*double", css)


def test_sheet_link_passes_origin(login, club, player, character):
    body = login(player).get(sheet(club, character)).content.decode()
    assert f"from=sheet&amp;character={character.pk}" in body or (
        f"from=sheet&character={character.pk}" in body
    )


def test_back_to_sheet(login, club, player, character):
    body = (
        login(player)
        .get(printurl(club, [character], f"&from=sheet&character={character.pk}"))
        .content.decode()
    )
    assert f'href="{sheet(club, character)}"' in body
    assert "Back to sheet" in body
    assert "Back to slips" not in body


def test_back_to_slips(login, club, player, character):
    body = login(player).get(printurl(club, [character])).content.decode()
    assert f'href="{slips(club)}"' in body
    assert "Back to slips" in body


def test_foreign_character_falls_back(login, club, player, character, foreign_character):
    url = printurl(club, [character], f"&from=sheet&character={foreign_character.pk}")
    body = login(player).get(url).content.decode()
    assert f'href="{slips(club)}"' in body
    assert f"/{foreign_character.pk}/" not in body.split("wm-toolbar")[1].split("</div>")[0]


def test_bad_character_falls_back(login, club, player, character):
    body = (
        login(player).get(printurl(club, [character], "&from=sheet&character=abc")).content.decode()
    )
    assert f'href="{slips(club)}"' in body
