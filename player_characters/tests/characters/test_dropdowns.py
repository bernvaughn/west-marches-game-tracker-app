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
    assert values == [""] + official + [OTHER]
    assert official == sorted(official)
    assert len(values) == expected_count + 2


def test_pronouns_dropdown_order(club, login, club_admin):
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, "pronouns")
    assert values == [""] + [value for value, _label in PRONOUNS_CHOICES] + [OTHER]


def test_alignment_dropdown_has_nine_alignments_no_other(club, login, club_admin):
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, "alignment")
    official = [value for value, _label in ALIGNMENT_CHOICES]
    assert values == [""] + official
    assert OTHER not in values
    assert official == sorted(official)
    assert len(values) == 10


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


def test_toggle_script_is_valid_javascript():
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "static" / "js" / "character_form.js"
    # A stray "]);" closing the pairs array stopped the whole script running.
    assert "]);\n  for" not in script.read_text()


def selected_value(soup, name):
    option = soup.select_one(f'select[name="{name}"] option[selected]')
    return option.get("value") if option else None


def test_freetext_inputs_do_not_print_the_current_dict(club, login, player, character):
    character.char_class = "Ranger"
    character.save()
    html = login(player).get(edit_url(club, character.pk)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    assert "{&#x27;name&#x27;:" not in html
    assert "{'name':" not in html
    for field in ("char_class", "species", "background", "pronouns"):
        freetext = soup.select_one(f'input[name="{field}_freetext"]')
        assert freetext.find_parent(class_="wm-field-pair") is None


def test_saved_alignment_with_other_casing_is_preselected(club, login, player, character):
    character.alignment = "Neutral good"
    character.save()
    soup = BeautifulSoup(
        login(player).get(edit_url(club, character.pk)).content.decode(), "html.parser"
    )
    assert selected_value(soup, "alignment") == "Neutral Good"


def test_unknown_saved_alignment_is_kept_as_an_option(club, login, player, character):
    character.alignment = "Unaligned"
    character.save()
    soup = BeautifulSoup(
        login(player).get(edit_url(club, character.pk)).content.decode(), "html.parser"
    )
    assert selected_value(soup, "alignment") == "Unaligned"


def test_custom_saved_value_preselects_other_with_freetext(club, login, player, character):
    character.char_class = "Artificer"
    character.save()
    soup = BeautifulSoup(
        login(player).get(edit_url(club, character.pk)).content.decode(), "html.parser"
    )
    assert selected_value(soup, "char_class") == OTHER
    assert soup.select_one('input[name="char_class_freetext"]').get("value") == "Artificer"
    # The "Current" value still shows the saved text, not "Other".
    titles = [span.get("title") for span in soup.select(".wm-field-current-value")]
    assert "Artificer" in titles
    assert OTHER not in titles


def test_blank_saved_dropdowns_select_the_blank_option(club, login, player, character):
    character.background = ""
    character.alignment = ""
    character.save()
    client = login(player)
    soup = BeautifulSoup(client.get(edit_url(club, character.pk)).content.decode(), "html.parser")
    assert selected_value(soup, "background") == ""
    assert selected_value(soup, "alignment") == ""
    # Posting the form as rendered keeps the blank fields blank.
    data = {}
    for el in soup.select("form.wm-character-form input[name], form.wm-character-form textarea"):
        if el.get("name") != "csrfmiddlewaretoken":
            data[el["name"]] = el.get("value") or el.get_text()
    for select in soup.select("form.wm-character-form select"):
        option = select.select_one("option[selected]") or select.select_one("option")
        data[select["name"]] = option.get("value")
    r = client.post(edit_url(club, character.pk), data)
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.background == ""
    assert character.alignment == ""


def test_create_page_dropdowns_default_to_blank(club, login, player):
    soup = BeautifulSoup(login(player).get(create_url(club)).content.decode(), "html.parser")
    for name in ("char_class", "species", "background", "pronouns", "alignment"):
        select = soup.select_one(f'select[name="{name}"]')
        first = select.select_one("option")
        assert first.get("value") == ""
        assert selected_value(soup, name) in (None, "")
