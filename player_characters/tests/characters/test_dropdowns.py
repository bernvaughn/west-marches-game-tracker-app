import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from player_characters.models import (
    ALIGNMENT_CHOICES,
    BACKGROUND_CHOICES,
    CLASS_CHOICES,
    OTHER,
    PRONOUNS_CHOICES,
    SPECIES_CHOICES,
    Character,
)


def create_url(club):
    return reverse("characters:create", kwargs={"club_slug": club.slug})


def edit_url(club, pk):
    return reverse("characters:edit", kwargs={"club_slug": club.slug, "pk": pk})


def option_values(soup, name):
    select = soup.select_one(f'select[name="{name}"]')
    assert select is not None, f"no <select name={name!r}> on the form"
    return [option.get("value") for option in select.select("option")]


@pytest.mark.parametrize(
    "field,choices,expected_count",
    [
        ("char_class", CLASS_CHOICES, 12),
        ("species", SPECIES_CHOICES, 11),
        ("background", BACKGROUND_CHOICES, 16),
    ],
)
def test_official_dropdown_is_alphabetized_with_other(
    club, login, club_admin, field, choices, expected_count
):
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, field)
    official = [value for value, _label in choices]
    assert values == official + [OTHER]
    assert official == sorted(official)
    assert len(values) == expected_count + 1


def test_pronouns_dropdown_order(club, login, club_admin):
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, "pronouns")
    assert values == [value for value, _label in PRONOUNS_CHOICES] + [OTHER]


def test_alignment_dropdown_has_nine_alignments_no_other(club, login, club_admin):
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, "alignment")
    official = [value for value, _label in ALIGNMENT_CHOICES]
    assert values == official
    assert OTHER not in values
    assert official == sorted(official)
    assert len(values) == 9


def test_freetext_inputs_render_on_the_form(club, login, club_admin):
    html = login(club_admin).get(create_url(club)).content.decode()
    for field in (
        "char_class_freetext",
        "species_freetext",
        "background_freetext",
        "pronouns_freetext",
    ):
        assert f'name="{field}"' in html
        assert f'id="id_{field}"' in html


@pytest.mark.parametrize("field", ["char_class", "species", "background", "pronouns"])
def test_other_saves_the_freetext_value(club, login, player, field):
    freetext = f"{field}_freetext"
    data = {"name": "Custom", field: OTHER, freetext: "My custom value"}
    r = login(player).post(create_url(club), data)
    assert r.status_code == 302
    character = Character.objects.get(name="Custom")
    assert getattr(character, field) == "My custom value"


def test_standard_option_saves_that_value(club, login, player):
    r = login(player).post(create_url(club), {"name": "Standard", "char_class": "Bard"})
    assert r.status_code == 302
    assert Character.objects.get(name="Standard").char_class == "Bard"


def test_other_saves_the_freetext_value_on_edit(club, login, player, character):
    r = login(player).post(
        edit_url(club, character.pk),
        {"name": "Renamed", "species": OTHER, "species_freetext": "My custom species"},
    )
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.species == "My custom species"


def test_blank_submission_still_creates_a_character(club, login, player):
    r = login(player).post(create_url(club), {"name": "Blank"})
    assert r.status_code == 302
    character = Character.objects.get(name="Blank")
    assert character.char_class == ""
    assert character.species == ""


def test_toggle_script_exists(client):
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "static" / "js" / "character_form.js"
    content = script.read_text()
    assert "id_char_class_freetext" in content
    assert 'select.value === "Other"' in content
