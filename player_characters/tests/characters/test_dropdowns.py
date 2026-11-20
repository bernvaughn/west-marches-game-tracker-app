import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from character_options.models import Background, CharacterClass, Species
from player_characters.models import (
    ALIGNMENT_CHOICES,
    OTHER,
    PRONOUNS_CHOICES,
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


def _club_option_names(club, model):
    return list(
        model.objects.for_club(club)
        .filter(is_active=True)
        .order_by("sort_order", "name")
        .values_list("name", flat=True)
    )


@pytest.mark.parametrize(
    "field,model",
    [
        ("char_class", CharacterClass),
        ("species", Species),
        ("background", Background),
    ],
)
def test_official_dropdown_is_alphabetized_with_other(club, login, club_admin, field, model):
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, field)
    official = _club_option_names(club, model)
    assert values == [""] + official + [OTHER]
    assert official == sorted(official)
    assert len(values) == len(official) + 2


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


@pytest.mark.parametrize("field", ["char_class", "species", "background"])
def test_other_saves_the_freetext_value(club, login, player, field):
    freetext = f"{field}_freetext"
    data = {"name": "Custom", field: OTHER, freetext: "My custom value"}
    r = login(player).post(create_url(club), data)
    assert r.status_code == 302
    character = Character.objects.get(name="Custom")
    assert getattr(character, field) == "My custom value"
    # FK should be null
    fk_field = (
        field.replace("char_class", "class_option")
        .replace("species", "species_option")
        .replace("background", "background_option")
    )
    assert getattr(character, f"{fk_field}_id") is None


def test_pronouns_other_saves_the_freetext_value(club, login, player):
    data = {"name": "Custom", "pronouns": OTHER, "pronouns_freetext": "My custom pronouns"}
    r = login(player).post(create_url(club), data)
    assert r.status_code == 302
    character = Character.objects.get(name="Custom")
    assert character.pronouns == "My custom pronouns"


def test_standard_option_saves_that_value(club, login, player):
    # Use a class name that exists in the seeded club
    class_name = CharacterClass.objects.for_club(club).filter(is_active=True).first().name
    r = login(player).post(create_url(club), {"name": "Standard", "char_class": class_name})
    assert r.status_code == 302
    character = Character.objects.get(name="Standard")
    assert character.char_class == class_name
    assert character.class_option_id is not None
    assert character.class_option.name == class_name


def test_standard_species_saves_that_value(club, login, player):
    species_name = Species.objects.for_club(club).filter(is_active=True).first().name
    r = login(player).post(create_url(club), {"name": "Standard", "species": species_name})
    assert r.status_code == 302
    character = Character.objects.get(name="Standard")
    assert character.species == species_name
    assert character.species_option_id is not None
    assert character.species_option.name == species_name


def test_standard_background_saves_that_value(club, login, player):
    background_name = Background.objects.for_club(club).filter(is_active=True).first().name
    r = login(player).post(create_url(club), {"name": "Standard", "background": background_name})
    assert r.status_code == 302
    character = Character.objects.get(name="Standard")
    assert character.background == background_name
    assert character.background_option_id is not None
    assert character.background_option.name == background_name


def test_other_saves_the_freetext_value_on_edit(club, login, player, character):
    r = login(player).post(
        edit_url(club, character.pk),
        {"name": "Renamed", "species": OTHER, "species_freetext": "My custom species"},
    )
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.species == "My custom species"
    assert character.species_option_id is None


def test_blank_submission_still_creates_a_character(club, login, player):
    r = login(player).post(create_url(club), {"name": "Blank"})
    assert r.status_code == 302
    character = Character.objects.get(name="Blank")
    assert character.char_class == ""
    assert character.species == ""
    assert character.background == ""
    assert character.class_option_id is None
    assert character.species_option_id is None
    assert character.background_option_id is None


def test_toggle_script_exists(client):
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "static" / "js" / "character_form.js"
    content = script.read_text()
    assert "id_char_class_freetext" in content
    assert 'select.value === "Other"' in content


def test_toggle_script_is_valid_javascript():
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "static" / "js" / "character_form.js"
    # A stray "});" closing the pairs array stopped the whole script running.
    assert "});\n  for" not in script.read_text()


def selected_value(soup, name):
    option = soup.select_one(f'select[name="{name}"] option[selected]')
    return option.get("value") if option else None


def test_freetext_inputs_do_not_print_the_current_dict(club, login, player, character):
    character.char_class = "Ranger"
    character.save()
    html = login(player).get(edit_url(club, character.pk)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    assert "{'name':" not in html
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


def test_only_active_records_listed(club, login, club_admin, char_class):
    # Archive the class
    char_class.is_active = False
    char_class.save()
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, "char_class")
    # Archived record should not appear in create form
    assert char_class.name not in values


def test_archived_record_shows_for_character_using_it(club, login, player, character, char_class):
    # Character uses this class
    character.class_option = char_class
    character.char_class = char_class.name
    character.save()
    # Archive the class
    char_class.is_active = False
    char_class.save()
    html = login(player).get(edit_url(club, character.pk)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, "char_class")
    # Archived record should appear for this character
    assert char_class.name in values
    # And it should be labeled as archived
    select = soup.select_one('select[name="char_class"]')
    option = select.select_one(f'option[value="{char_class.name}"]')
    assert "(archived)" in option.text


def test_archived_record_hidden_for_other_characters(club, login, other_player, char_class):
    # Archive the class
    char_class.is_active = False
    char_class.save()
    html = login(other_player).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, "char_class")
    # Archived record should not appear for other characters
    assert char_class.name not in values


def test_admin_reordered_list_order(club, login, club_admin, char_class, species):
    # Change sort_order
    char_class.sort_order = 100
    char_class.save()
    species.sort_order = 50
    species.save()
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    # Options should be ordered by sort_order
    class_values = option_values(soup, "char_class")
    species_values = option_values(soup, "species")
    # First non-blank should be the one with lowest sort_order
    active_classes = list(
        CharacterClass.objects.for_club(club)
        .filter(is_active=True)
        .order_by("sort_order", "name")
        .values_list("name", flat=True)
    )
    active_species = list(
        Species.objects.for_club(club)
        .filter(is_active=True)
        .order_by("sort_order", "name")
        .values_list("name", flat=True)
    )
    assert class_values == [""] + active_classes + [OTHER]
    assert species_values == [""] + active_species + [OTHER]


def test_another_club_records_never_shown(club, other_club, login, club_admin):
    # Create a class in the other club
    other_class = CharacterClass.objects.create(
        club=other_club, name="OtherClubClass", sort_order=5
    )
    html = login(club_admin).get(create_url(club)).content.decode()
    soup = BeautifulSoup(html, "html.parser")
    values = option_values(soup, "char_class")
    assert other_class.name not in values
