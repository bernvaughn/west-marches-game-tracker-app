"""Tests for CharacterForm with club-scoped character options."""

import pytest
import re
from django.urls import reverse

from character_options.models import Background, CharacterClass, Species
from player_characters.models import Character, OTHER


def create_url(club):
    return reverse("characters:create", kwargs={"club_slug": club.slug})


def edit_url(club, pk):
    return reverse("characters:edit", kwargs={"club_slug": club.slug, "pk": pk})


@pytest.fixture
def club_with_options(club):
    """Ensure club has seeded options."""
    # club fixture already seeds defaults
    return club


class TestListedValueSetsFK:
    """Saving a listed choice sets the FK and the text name."""

    def test_class_create_sets_fk_and_text(self, club_with_options, login, player):
        class_name = CharacterClass.objects.for_club(club_with_options).filter(is_active=True).first().name
        r = login(player).post(create_url(club_with_options), {"name": "Test", "char_class": class_name})
        assert r.status_code == 302
        character = Character.objects.get(name="Test")
        assert character.char_class == class_name
        assert character.class_option_id is not None
        assert character.class_option.name == class_name

    def test_species_create_sets_fk_and_text(self, club_with_options, login, player):
        species_name = Species.objects.for_club(club_with_options).filter(is_active=True).first().name
        r = login(player).post(create_url(club_with_options), {"name": "Test", "species": species_name})
        assert r.status_code == 302
        character = Character.objects.get(name="Test")
        assert character.species == species_name
        assert character.species_option_id is not None
        assert character.species_option.name == species_name

    def test_background_create_sets_fk_and_text(self, club_with_options, login, player):
        background_name = Background.objects.for_club(club_with_options).filter(is_active=True).first().name
        r = login(player).post(create_url(club_with_options), {"name": "Test", "background": background_name})
        assert r.status_code == 302
        character = Character.objects.get(name="Test")
        assert character.background == background_name
        assert character.background_option_id is not None
        assert character.background_option.name == background_name

    def test_class_edit_sets_fk_and_text(self, club_with_options, login, player, character):
        class_name = CharacterClass.objects.for_club(club_with_options).filter(is_active=True).first().name
        r = login(player).post(edit_url(club_with_options, character.pk), {"name": "Test", "char_class": class_name})
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.char_class == class_name
        assert character.class_option_id is not None
        assert character.class_option.name == class_name

    def test_species_edit_sets_fk_and_text(self, club_with_options, login, player, character):
        species_name = Species.objects.for_club(club_with_options).filter(is_active=True).first().name
        r = login(player).post(edit_url(club_with_options, character.pk), {"name": "Test", "species": species_name})
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.species == species_name
        assert character.species_option_id is not None
        assert character.species_option.name == species_name

    def test_background_edit_sets_fk_and_text(self, club_with_options, login, player, character):
        background_name = Background.objects.for_club(club_with_options).filter(is_active=True).first().name
        r = login(player).post(edit_url(club_with_options, character.pk), {"name": "Test", "background": background_name})
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.background == background_name
        assert character.background_option_id is not None
        assert character.background_option.name == background_name


class TestOtherClearsFK:
    """Saving 'Other' clears an existing FK and stores freetext."""

    def test_class_other_clears_fk(self, club_with_options, login, player, character):
        # First set a class
        class_name = CharacterClass.objects.for_club(club_with_options).filter(is_active=True).first().name
        character.class_option = CharacterClass.objects.for_club(club_with_options).get(name=class_name)
        character.char_class = class_name
        character.save()
        assert character.class_option_id is not None

        # Now save with Other
        r = login(player).post(
            edit_url(club_with_options, character.pk),
            {"name": "Test", "char_class": OTHER, "char_class_freetext": "My Custom Class"}
        )
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.char_class == "My Custom Class"
        assert character.class_option_id is None

    def test_species_other_clears_fk(self, club_with_options, login, player, character):
        species_name = Species.objects.for_club(club_with_options).filter(is_active=True).first().name
        character.species_option = Species.objects.for_club(club_with_options).get(name=species_name)
        character.species = species_name
        character.save()
        assert character.species_option_id is not None

        r = login(player).post(
            edit_url(club_with_options, character.pk),
            {"name": "Test", "species": OTHER, "species_freetext": "My Custom Species"}
        )
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.species == "My Custom Species"
        assert character.species_option_id is None

    def test_background_other_clears_fk(self, club_with_options, login, player, character):
        background_name = Background.objects.for_club(club_with_options).filter(is_active=True).first().name
        character.background_option = Background.objects.for_club(club_with_options).get(name=background_name)
        character.background = background_name
        character.save()
        assert character.background_option_id is not None

        r = login(player).post(
            edit_url(club_with_options, character.pk),
            {"name": "Test", "background": OTHER, "background_freetext": "My Custom Background"}
        )
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.background == "My Custom Background"
        assert character.background_option_id is None

    def test_other_with_blank_freetext_clears_fk_and_text(self, club_with_options, login, player, character):
        class_name = CharacterClass.objects.for_club(club_with_options).filter(is_active=True).first().name
        character.class_option = CharacterClass.objects.for_club(club_with_options).get(name=class_name)
        character.char_class = class_name
        character.save()

        r = login(player).post(
            edit_url(club_with_options, character.pk),
            {"name": "Test", "char_class": OTHER, "char_class_freetext": ""}
        )
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.char_class == ""
        assert character.class_option_id is None


class TestLegacyValues:
    """Legacy values match or stay custom."""

    def test_legacy_value_matches_existing_record(self, club_with_options, login, player):
        """A value that matches an existing record (case-insensitive) should link."""
        class_name = CharacterClass.objects.for_club(club_with_options).filter(is_active=True).first().name
        # Post with different casing
        r = login(player).post(create_url(club_with_options), {"name": "Test", "char_class": class_name.lower()})
        assert r.status_code == 302
        character = Character.objects.get(name="Test")
        assert character.char_class == class_name  # Canonical name
        assert character.class_option_id is not None
        assert character.class_option.name == class_name

    def test_legacy_value_no_match_stays_custom(self, club_with_options, login, player):
        """A value with no matching record stays as custom text, FK null."""
        r = login(player).post(create_url(club_with_options), {"name": "Test", "char_class": "NonExistentClass"})
        assert r.status_code == 302
        character = Character.objects.get(name="Test")
        assert character.char_class == "NonExistentClass"
        assert character.class_option_id is None

    def test_value_from_another_club_stays_custom(self, club_with_options, other_club, login, player):
        """A value matching a record in another club stays custom."""
        other_class = CharacterClass.objects.create(club=other_club, name="OtherClubClass")
        r = login(player).post(create_url(club_with_options), {"name": "Test", "char_class": other_class.name})
        assert r.status_code == 302
        character = Character.objects.get(name="Test")
        assert character.char_class == "OtherClubClass"
        assert character.class_option_id is None


class TestRenamedRecord:
    """Renamed record shows the new name preselected."""

    def test_renamed_class_shows_new_name(self, club_with_options, login, player, character, char_class):
        # Character must have the class_option set to test renaming
        character.class_option = char_class
        character.char_class = char_class.name
        character.save()

        # Rename the class
        char_class.name = "Renamed Fighter"
        char_class.save()

        # Edit page should show new name
        html = login(player).get(edit_url(club_with_options, character.pk)).content.decode()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        selected = soup.select_one('select[name="char_class"] option[selected]')
        assert selected.get("value") == "Renamed Fighter"

        # Saving should keep the FK and use new name
        r = login(player).post(edit_url(club_with_options, character.pk), {"name": "Test", "char_class": "Renamed Fighter"})
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.char_class == "Renamed Fighter"
        assert character.class_option_id == char_class.id


class TestFKNullTextMatching:
    """FK null + text matching a record preselects it; saving links it."""

    def test_null_fk_matching_text_preselects_record(self, club_with_options, login, player, membership):
        """Character with FK null but text matching a record should preselect that record."""
        class_name = CharacterClass.objects.for_club(club_with_options).filter(is_active=True).first().name
        character = Character.objects.create(
            club=club_with_options,
            owner=membership,
            name="Test",
            char_class=class_name,
            class_option=None,
        )
        # Edit page should preselect the matching record
        html = login(player).get(edit_url(club_with_options, character.pk)).content.decode()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        selected = soup.select_one('select[name="char_class"] option[selected]')
        assert selected.get("value") == class_name

        # Saving should link the FK
        r = login(player).post(edit_url(club_with_options, character.pk), {"name": "Test", "char_class": class_name})
        assert r.status_code == 302
        character.refresh_from_db()
        assert character.class_option_id is not None
        assert character.class_option.name == class_name


class TestCustomFlags:
    """Flag text present in the form; 'custom' badge on edit and detail when custom; absent when linked."""

    def test_other_flag_shows_on_create(self, club_with_options, login, club_admin):
        """Other flag shows for class and background on create."""
        html = login(club_admin).get(create_url(club_with_options)).content.decode()
        assert "Custom value: no starting equipment for this char_class." in html
        assert "Custom value: no starting equipment for this background." in html
        assert "Custom value" in html  # species flag

    def test_custom_badge_on_edit_when_custom(self, club_with_options, login, player, character):
        """Custom badge shows on edit when FK null and text set."""
        character.char_class = "Custom Class"
        character.class_option = None
        character.save()
        html = login(player).get(edit_url(club_with_options, character.pk)).content.decode()
        assert "custom" in html.lower()
        assert "wm-badge--warning" in html

    def test_no_badge_on_edit_when_linked(self, club_with_options, login, player, character):
        """No custom badge when linked to a record."""
        class_name = CharacterClass.objects.for_club(club_with_options).filter(is_active=True).first().name
        character.char_class = class_name
        character.class_option = CharacterClass.objects.for_club(club_with_options).get(name=class_name)
        character.save()
        html = login(player).get(edit_url(club_with_options, character.pk)).content.decode()
        # Should not have custom badge for class
        assert 'class="wm-badge wm-badge--warning">custom</span>' not in html


class TestDetailPageBadges:
    """Custom badge on detail page."""

    def test_custom_badge_on_detail_when_custom(self, club_with_options, login, player, character):
        print(f'DEBUG: character pk={character.pk}, char_class={character.char_class}, class_option_id={character.class_option_id}')
        character.char_class = "Custom Class"
        character.class_option = None
        character.save()
        print(f'AFTER SAVE: char_class={character.char_class}, class_option_id={character.class_option_id}')
        # Reload from DB to be sure
        character.refresh_from_db()
        print(f'AFTER REFRESH: char_class={character.char_class}, class_option_id={character.class_option_id}')
        detail_url = reverse("characters:detail", kwargs={"club_slug": club_with_options.slug, "pk": character.pk})
        html = login(player).get(detail_url).content.decode()
        # Badge uses wm-badge--warning class
        # Debug: print header section
        header_match = re.search(r'<header class="wm-sheet-header">(.*?)</header>', html, re.DOTALL)
        if header_match:
            header = header_match.group(1)
            print(f'HEADER: {header[:500]}')
        else:
            print('NO HEADER FOUND')
        assert "wm-badge--warning" in html
        assert "custom" in html.lower()

    def test_no_badge_on_detail_when_linked(self, club_with_options, login, player, character):
        class_name = CharacterClass.objects.for_club(club_with_options).filter(is_active=True).first().name
        character.char_class = class_name
        character.class_option = CharacterClass.objects.for_club(club_with_options).get(name=class_name)
        character.save()
        detail_url = reverse("characters:detail", kwargs={"club_slug": club_with_options.slug, "pk": character.pk})
        html = login(player).get(detail_url).content.decode()
        # Should not have custom badge for class
        assert 'class="wm-badge wm-badge--warning">custom</span>' not in html