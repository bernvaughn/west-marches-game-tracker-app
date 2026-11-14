import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = [pytest.mark.story("U89"), pytest.mark.django_db]

CSS = Path(settings.BASE_DIR) / "static" / "css"


def printurl(club, *chars):
    q = "&".join(f"characters={c.pk}" for c in chars)
    return reverse("characters:slips_print", args=[club.slug]) + "?" + q


def test_main_part_order(login, club, player, character):
    character.pronouns = "she/her"
    character.species = "Elf"
    character.char_class = "Rogue"
    character.level = 4
    character.armor_class = 15
    character.perception_bonus = 3
    character.max_hp = 22
    character.save()
    body = login(player).get(printurl(club, character)).content.decode()
    order = [
        "adventurer's pass",
        'class="wm-wordmark',
        "she/her",
        "played by <b>",
        ">Species<",
        ">Class<",
        ">Level<",
        ">AC<",
        ">Passive Perc.<",
        ">Max HP<",
        "Downtime Market",
    ]
    body = body[body.index("wm-slip-sheet") :]
    idx = [body.index(t) for t in order]
    assert idx == sorted(idx)


def test_blank_pills_left_out(login, club, player, character):
    body = login(player).get(printurl(club, character)).content.decode()
    for label in ("Species", "Class", "Level", "AC", "Max HP", "Passive Perc."):
        assert f">{label}<" not in body
    assert "wm-slip-pills" not in body.split('class="wm-slip-sheet"')[1]


def test_ability_blocks(login, club, player, character):
    character.strength = 14
    character.dexterity = 8
    character.save()
    body = login(player).get(printurl(club, character)).content.decode()
    assert body.count('class="wm-slip-ability"') == 6
    for abbr in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        assert f">{abbr}<" in body
    assert ">+2<" in body and ">−1<" in body and ">—<" in body


def test_css_rules():
    comp = (CSS / "components.css").read_text()
    assert ".wm-pass {" in comp and "mask" in comp and "dashed" in comp
    chars = (CSS / "areas" / "characters.css").read_text()
    block = chars[chars.index("/* Character slips") :]
    block = block[: block.index("\n/*", 5)] if "\n/*" in block[5:] else block
    assert "repeat(2, 4in)" in block and "1.75in" in block
    assert not re.search(r"font-size:\s*[\d.]+(rem|px)", block)
    for v in re.findall(r"font-size:\s*([\d.]+)pt", block):
        assert float(v) >= 7


def test_cross_club_rejected(login, club, game_master, foreign_character):
    body = login(game_master).get(printurl(club, foreign_character)).content.decode()
    assert "not available" in body and foreign_character.name not in body
