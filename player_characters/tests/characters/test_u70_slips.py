import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from player_characters.models import Character

pytestmark = [pytest.mark.story("U70"), pytest.mark.django_db]


def picker(club):
    return reverse("characters:slips", args=[club.slug])


def printurl(club, *chars):
    q = "&".join(f"characters={c.pk}" for c in chars)
    return reverse("characters:slips_print", args=[club.slug]) + "?" + q


@pytest.fixture
def everyone(character, other_character, gm_character, foreign_character):
    return character, other_character, gm_character


def test_gm_and_admin_see_all(login, club, game_master, club_admin, everyone, foreign_character):
    for user in (game_master, club_admin):
        body = login(user).get(picker(club)).content.decode()
        for c in everyone:
            assert c.name in body
        assert foreign_character.name not in body


def test_player_sees_only_own(login, club, player, everyone):
    body = login(player).get(picker(club)).content.decode()
    assert everyone[0].name in body
    assert everyone[1].name not in body
    assert everyone[2].name not in body


def test_cross_club_id_rejected(login, club, game_master, foreign_character):
    body = login(game_master).get(printurl(club, foreign_character)).content.decode()
    assert "not available" in body
    assert "wm-slip-sheet" not in body
    assert foreign_character.name not in body


def test_player_cannot_print_other(login, club, player, other_character):
    body = login(player).get(printurl(club, other_character)).content.decode()
    assert "not available" in body
    assert 'wm-slip"' not in body


def test_slip_fields(login, club, player, character):
    character.pronouns = "she/her"
    character.perception_bonus = 3
    character.level = 4
    character.char_class = "Rogue"
    character.species = "Elf"
    character.save()
    body = login(player).get(printurl(club, character)).content.decode()
    assert player.display_name in body
    for t in (
        character.name,
        "Pronouns: she/her",
        "Passive Perception: 13",
        "Level: 4",
        "Class: Rogue",
        "Species: Elf",
    ):
        assert t in body


def test_blank_shows_dash(login, club, player, character):
    body = login(player).get(printurl(club, character)).content.decode()
    assert "Passive Perception: —" in body


def test_thirteen_make_two_sheets(login, club, game_master, character):
    chars = [character]
    for i in range(12):
        chars.append(Character.objects.create(club=club, owner=character.owner, name=f"Extra {i}"))
    body = login(game_master).get(printurl(club, *chars)).content.decode()
    assert body.count('<section class="wm-slip-sheet">') == 2
    sheets = body.split('<section class="wm-slip-sheet">')[1:]
    assert [s.count('<article class="wm-slip">') for s in sheets] == [12, 1]


def test_css():
    p = (Path(settings.BASE_DIR) / "static" / "css" / "print.css").read_text()
    assert re.search(r"@page slips\s*{[^}]*margin:\s*0", p)
    assert re.search(r"\.wm-slip-sheet[^}]*page:\s*slips", p)
    c = (Path(settings.BASE_DIR) / "static" / "css" / "areas" / "characters.css").read_text()
    assert re.search(r"\.wm-slip\s*{[^}]*dashed", c)


def test_sheet_link(login, club, player, character):
    body = (
        login(player)
        .get(reverse("characters:detail", args=[club.slug, character.pk]))
        .content.decode()
    )
    assert f"slips/print/?characters={character.pk}" in body
    assert "Print slip</a>" in body
    assert "data-wm-tooltip" in body


def test_menu_entry(login, club, player, game_master, character):
    for u in (player, game_master):
        assert "Character slips" in login(u).get(picker(club)).content.decode()


def test_no_selection(login, club, player, character):
    url = reverse("characters:slips_print", args=[club.slug])
    assert "Tick at least one character." in login(player).get(url).content.decode()
