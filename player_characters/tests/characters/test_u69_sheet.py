import pytest

from player_characters import sheet as sh
from player_characters.models import Character

from .test_sheet import u  # noqa: F401


@pytest.mark.story("U69")
@pytest.mark.parametrize("score,mod", [(1, "−5"), (10, "+0"), (11, "+0"), (20, "+5"), (30, "+10")])
def test_modifiers(score, mod):
    assert sh.format_modifier(sh.ability_modifier(score)) == mod


@pytest.mark.story("U69")
def test_blank_modifier_is_dash():
    assert sh.ability_modifier(None) is None
    assert sh.format_modifier(None) == "—"


@pytest.mark.story("U69")
@pytest.mark.parametrize(
    "bonus,label", [(3, "13 (10 + 3)"), (-2, "8 (10 − 2)"), (0, "10 (10 + 0)"), (None, "—")]
)
def test_passive_perception(bonus, label):
    assert sh.passive_perception_label(bonus) == label


FULL = {
    "name": "Renamed",
    "level": 3,
    "char_class": "Wizard",
    "species": "Gnome",
    "pronouns": "she/her",
    "alignment": "Chaotic good",
    "strength": 8,
    "dexterity": 14,
    "constitution": 12,
    "intelligence": 20,
    "wisdom": 11,
    "charisma": 30,
    "armor_class": 13,
    "perception_bonus": 3,
    "xp": 900,
    "description": "Tall tales.",
}


@pytest.mark.story("U69")
def test_fields_save_and_show(club, login, player, funded):
    c = login(player)
    r = c.post(u("characters:edit", club, funded.pk), FULL)
    assert r.status_code == 302
    funded.refresh_from_db()
    assert funded.char_class == "Wizard" and funded.intelligence == 20 and funded.xp == 900
    html = c.get(u("characters:detail", club, funded.pk)).content.decode()
    for text in ["Wizard", "Gnome", "she/her", "13 (10 + 3)", "900", "Tall tales.", "+10", "−1"]:
        assert text in html


@pytest.mark.story("U69")
@pytest.mark.parametrize(
    "bad",
    [{"strength": 0}, {"strength": 31}, {"armor_class": 41}, {"xp": -1}, {"perception_bonus": 31}],
)
def test_validation(club, login, player, funded, bad):
    r = login(player).post(u("characters:edit", club, funded.pk), {**FULL, **bad})
    assert r.status_code == 200


@pytest.mark.story("U69")
def test_blank_is_allowed(club, login, player, funded):
    r = login(player).post(u("characters:edit", club, funded.pk), {"name": "Plain"})
    assert r.status_code == 302
    funded.refresh_from_db()
    assert funded.strength is None and funded.perception_bonus is None
    html = login(player).get(u("characters:detail", club, funded.pk)).content.decode()
    assert "Passive Perception" in html


@pytest.mark.story("U69")
def test_removed_fields_gone(club, login, player, funded):
    names = {f.name for f in Character._meta.get_fields()}
    assert not names & {"notes", "stats", "details"}
    html = login(player).get(u("characters:edit", club, funded.pk)).content.decode()
    for n in ["notes", "stats", "details"]:
        assert f'name="{n}"' not in html


@pytest.mark.story("U69")
def test_edit_page_has_sheet_boxes(club, login, player, funded):
    html = login(player).get(u("characters:edit", club, funded.pk)).content.decode()
    assert html.count("wm-sheet-box") >= 3
    for i in ["form-abilities", "form-combat", "form-description"]:
        assert i in html


@pytest.mark.story("U69")
def test_directory_and_index_show_class_species(club, login, player, game_master, funded):
    funded.char_class, funded.species = "Bard", "Tiefling"
    funded.save()
    for who, name in [(player, "characters:directory"), (game_master, "characters:index")]:
        html = login(who).get(u(name, club)).content.decode()
        assert "Bard" in html and "Tiefling" in html


@pytest.mark.story("U79")
def test_ledger_hidden_in_print_and_menu_fixed(club, login, player, funded):
    html = login(player).get(u("characters:detail", club, funded.pk)).content.decode()
    assert "wm-sheet-ledger-box" in html
    assert "&quot;strategy&quot;" in html or '"strategy":"fixed"' in html
    from pathlib import Path

    css = Path("static/css/areas/characters.css").read_text()
    assert ".wm-sheet-ledger-box { display: none; }" in css
