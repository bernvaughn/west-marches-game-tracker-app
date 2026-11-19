import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from player_characters.character_forms import CharacterForm
from player_characters.sheet import edit_current_values


def edit_url(club, pk):
    return reverse("characters:edit", kwargs={"club_slug": club.slug, "pk": pk})


def current_value(soup, field_name):
    pair = soup.select_one(f'[name="{field_name}"]').find_parent(class_="wm-field-pair")
    return pair.select_one(".wm-field-current-value").get_text(strip=True)


@pytest.mark.story("U69")
def test_every_field_shows_its_saved_value(club, login, player, character):
    character.level = 6
    character.char_class = "Ranger"
    character.species = "Wood Elf"
    character.pronouns = "she/her"
    character.alignment = "Neutral Good"
    character.strength = 18
    character.dexterity = 14
    character.constitution = 12
    character.intelligence = 10
    character.wisdom = 16
    character.charisma = 8
    character.armor_class = 16
    character.max_hp = 34
    character.perception_bonus = 3
    character.xp = 2400
    character.description = "A keen-eyed ranger of the deep woods."
    character.save()
    soup = BeautifulSoup(
        login(player).get(edit_url(club, character.pk)).content.decode(), "html.parser"
    )
    expected = {
        "name": "Aria",
        "level": "6",
        "char_class": "Ranger",
        "species": "Wood Elf",
        "pronouns": "she/her",
        "alignment": "Neutral Good",
        "strength": "18 (+4)",
        "dexterity": "14 (+2)",
        "constitution": "12 (+1)",
        "intelligence": "10 (+0)",
        "wisdom": "16 (+3)",
        "charisma": "8 (−1)",
        "armor_class": "16",
        "max_hp": "34",
        "perception_bonus": "3",
        "xp": "2400",
        "description": "A keen-eyed ranger of the deep woods.",
    }
    for name, text in expected.items():
        assert current_value(soup, name) == text, f"wrong current value for {name}"


@pytest.mark.story("U69")
@pytest.mark.parametrize(
    "score,label",
    [
        (18, "18 (+4)"),
        (10, "10 (+0)"),
        (9, "9 (−1)"),
        (3, "3 (−4)"),
    ],
)
def test_ability_current_shows_modifier(club, login, player, character, score, label):
    character.strength = score
    character.save()
    soup = BeautifulSoup(
        login(player).get(edit_url(club, character.pk)).content.decode(), "html.parser"
    )
    assert current_value(soup, "strength") == label


@pytest.mark.story("U69")
def test_blank_field_shows_a_dash(club, login, player, character):
    # New characters default to 10, but an explicitly blank character still shows a dash.
    character.level = None
    character.strength = None
    character.dexterity = None
    character.description = ""
    character.save()
    soup = BeautifulSoup(
        login(player).get(edit_url(club, character.pk)).content.decode(), "html.parser"
    )
    for field in ("level", "strength", "dexterity", "description"):
        assert current_value(soup, field) == "—", f"{field} should show a dash"


@pytest.mark.story("U69")
def test_current_uses_saved_values_after_a_failed_post(club, login, player, character):
    character.name = "Aria"
    character.level = 5
    character.save()
    url = edit_url(club, character.pk)
    r = login(player).post(url, {"name": "Submitted Name", "level": 0})
    assert r.status_code == 200
    soup = BeautifulSoup(r.content.decode(), "html.parser")
    assert current_value(soup, "name") == "Aria"
    assert current_value(soup, "level") == "5"


@pytest.mark.story("U69")
def test_create_page_has_no_current_column(club, login, club_admin):
    html = (
        login(club_admin)
        .get(reverse("characters:create", kwargs={"club_slug": club.slug}))
        .content.decode()
    )
    assert "wm-field-current" not in html


@pytest.mark.story("U69")
def test_create_form_shows_default_ten(club, login, club_admin):
    html = (
        login(club_admin)
        .get(reverse("characters:create", kwargs={"club_slug": club.slug}))
        .content.decode()
    )
    for field in (
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    ):
        assert f'name="{field}" value="10"' in html


@pytest.mark.story("U69")
def test_helper_formats_the_mapping(club, login, player, character):
    character.level = 5
    character.strength = 18
    character.description = "  spaced  "
    character.save()
    form = CharacterForm(instance=character, club=club)
    values = edit_current_values(form)
    assert values["level"] == "5"
    assert values["strength"] == "18 (+4)"
    assert values["description"] == "spaced"
    assert values["name"] == "Aria"
