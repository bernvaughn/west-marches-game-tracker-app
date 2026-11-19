"""Tests for the link_character_options data migration."""

import pytest
from io import StringIO
from django.core.management import call_command
from django.db import connection

from character_options.models import Background, CharacterClass, Species
from player_characters.models import Character
from accounts.models import Membership, User


@pytest.fixture
def seeded_club(db):
    """Club with seeded options."""
    from accounts.models import Club
    from character_options.services import seed_default_options
    club = Club.objects.create(name="Test Club", slug="test-club")
    seed_default_options(club)
    return club


@pytest.fixture
def unseeded_club(db):
    """Club without seeded options."""
    from accounts.models import Club
    return Club.objects.create(name="Unseeded Club", slug="unseeded-club")


@pytest.fixture
def membership(seeded_club, player):
    return Membership.objects.get(user=player, club=seeded_club)


@pytest.fixture
def player(db):
    user = User.objects.create_user("player@example.com", password="pw", display_name="Player")
    return user


def run_migration(apps, schema_editor):
    """Run the link_characters migration function."""
    from player_characters.migrations.0015_link_character_options import link_characters
    link_characters(apps, schema_editor)


class TestLinkCharacterOptionsMigration:
    """Test the data migration that links existing characters to option records."""

    def test_case_insensitive_match(self, seeded_club, membership, capsys):
        """Case-insensitive exact name match links the record."""
        class_name = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first().name
        Character.objects.create(
            club=seeded_club,
            owner=membership,
            name="TestChar",
            char_class=class_name.lower(),  # Different case
            class_option=None,
        )

        # Run migration
        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        character = Character.objects.get(name="TestChar")
        assert character.class_option_id is not None
        assert character.class_option.name == class_name
        assert character.char_class == class_name  # Canonical name

    def test_trimmed_match(self, seeded_club, membership):
        """Trimmed whitespace match links the record."""
        class_name = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first().name
        Character.objects.create(
            club=seeded_club,
            owner=membership,
            name="TestChar",
            char_class=f"  {class_name}  ",  # With whitespace
            class_option=None,
        )

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        character = Character.objects.get(name="TestChar")
        assert character.class_option_id is not None
        assert character.class_option.name == class_name
        assert character.char_class == class_name  # Trimmed canonical name

    def test_unmatched_stays_custom_text_unchanged(self, seeded_club, membership, capsys):
        """Unmatched value stays as custom text, FK null, text unchanged."""
        Character.objects.create(
            club=seeded_club,
            owner=membership,
            name="TestChar",
            char_class="My Custom Class",
            class_option=None,
        )

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        character = Character.objects.get(name="TestChar")
        assert character.class_option_id is None
        assert character.char_class == "My Custom Class"  # Text unchanged

    def test_archived_record_matches(self, seeded_club, membership):
        """Archived record matches and links."""
        class_obj = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first()
        class_name = class_obj.name
        # Archive it
        class_obj.is_active = False
        class_obj.save()

        Character.objects.create(
            club=seeded_club,
            owner=membership,
            name="TestChar",
            char_class=class_name,
            class_option=None,
        )

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        character = Character.objects.get(name="TestChar")
        assert character.class_option_id is not None
        assert character.class_option.name == class_name
        assert character.class_option.is_active is False  # Still archived

    def test_other_club_not_matched(self, seeded_club, unseeded_club, membership):
        """Record from another club is not matched."""
        other_class = CharacterClass.objects.create(club=unseeded_club, name="OtherClubClass")

        Character.objects.create(
            club=seeded_club,
            owner=membership,
            name="TestChar",
            char_class=other_class.name,
            class_option=None,
        )

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        character = Character.objects.get(name="TestChar")
        assert character.class_option_id is None
        assert character.char_class == "OtherClubClass"  # Text unchanged

    def test_already_linked_untouched(self, seeded_club, membership):
        """Already linked character is not modified."""
        class_obj = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first()
        character = Character.objects.create(
            club=seeded_club,
            owner=membership,
            name="TestChar",
            char_class=class_obj.name,
            class_option=class_obj,
        )
        original_fk = character.class_option_id

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        character.refresh_from_db()
        assert character.class_option_id == original_fk

    def test_printed_counts(self, seeded_club, membership, capsys):
        """Migration prints counts per field: linked, left custom, blank."""
        class_name = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first().name
        species_name = Species.objects.for_club(seeded_club).filter(is_active=True).first().name
        background_name = Background.objects.for_club(seeded_club).filter(is_active=True).first().name

        # Create characters with various states
        Character.objects.create(
            club=seeded_club, owner=membership, name="LinkedClass",
            char_class=class_name.lower(), class_option=None,
        )
        Character.objects.create(
            club=seeded_club, owner=membership, name="CustomClass",
            char_class="Custom Class", class_option=None,
        )
        Character.objects.create(
            club=seeded_club, owner=membership, name="BlankClass",
            char_class="", class_option=None,
        )
        Character.objects.create(
            club=seeded_club, owner=membership, name="LinkedSpecies",
            species=species_name.lower(), species_option=None,
        )
        Character.objects.create(
            club=seeded_club, owner=membership, name="CustomSpecies",
            species="Custom Species", species_option=None,
        )
        Character.objects.create(
            club=seeded_club, owner=membership, name="BlankSpecies",
            species="", species_option=None,
        )
        Character.objects.create(
            club=seeded_club, owner=membership, name="LinkedBackground",
            background=background_name.lower(), background_option=None,
        )
        Character.objects.create(
            club=seeded_club, owner=membership, name="CustomBackground",
            background="Custom Background", background_option=None,
        )
        Character.objects.create(
            club=seeded_club, owner=membership, name="BlankBackground",
            background="", background_option=None,
        )

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        captured = capsys.readouterr()
        output = captured.out

        # Check counts for each field
        assert "char_class: linked=1, left_custom=1, blank=1" in output
        assert "species: linked=1, left_custom=1, blank=1" in output
        assert "background: linked=1, left_custom=1, blank=1" in output

    def test_idempotent_re_run(self, seeded_club, membership):
        """Re-running the migration is idempotent."""
        class_name = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first().name
        Character.objects.create(
            club=seeded_club,
            owner=membership,
            name="TestChar",
            char_class=class_name.lower(),
            class_option=None,
        )

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)
            # Run again
            run_migration(apps, schema_editor)

        character = Character.objects.get(name="TestChar")
        assert character.class_option_id is not None
        assert character.class_option.name == class_name

    def test_reverse_is_noop(self, seeded_club, membership):
        """Reverse migration is a no-op."""
        from player_characters.migrations.0015_link_character_options import reverse_noop
        from django.apps import apps

        class_name = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first().name
        Character.objects.create(
            club=seeded_club,
            owner=membership,
            name="TestChar",
            char_class=class_name.lower(),
            class_option=None,
        )

        with connection.schema_editor() as schema_editor:
            # Forward
            run_migration(apps, schema_editor)
            character = Character.objects.get(name="TestChar")
            assert character.class_option_id is not None

            # Reverse
            reverse_noop(apps, schema_editor)
            character.refresh_from_db()
            # FK should still be set (reverse is noop)
            assert character.class_option_id is not None

    def test_all_three_fields_processed(self, seeded_club, membership, capsys):
        """All three fields (class, species, background) are processed."""
        class_name = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first().name
        species_name = Species.objects.for_club(seeded_club).filter(is_active=True).first().name
        background_name = Background.objects.for_club(seeded_club).filter(is_active=True).first().name

        Character.objects.create(
            club=seeded_club, owner=membership, name="AllFields",
            char_class=class_name.lower(), class_option=None,
            species=species_name.lower(), species_option=None,
            background=background_name.lower(), background_option=None,
        )

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        character = Character.objects.get(name="AllFields")
        assert character.class_option_id is not None
        assert character.species_option_id is not None
        assert character.background_option_id is not None
        assert character.char_class == class_name
        assert character.species == species_name
        assert character.background == background_name

        captured = capsys.readouterr()
        assert "char_class: linked=1" in captured.out
        assert "species: linked=1" in captured.out
        assert "background: linked=1" in captured.out

    def test_multiple_clubs_processed_separately(self, seeded_club, unseeded_club, membership, player):
        """Each club's characters are processed independently."""
        # Create a user for the unseeded club
        other_user = User.objects.create_user("other@example.com", password="pw", display_name="Other")
        other_membership = Membership.objects.create(user=other_user, club=unseeded_club)

        class_name_seeded = CharacterClass.objects.for_club(seeded_club).filter(is_active=True).first().name
        Character.objects.create(
            club=seeded_club, owner=membership, name="SeededClubChar",
            char_class=class_name_seeded.lower(), class_option=None,
        )

        # Unseeded club has no options, so should stay custom
        Character.objects.create(
            club=unseeded_club, owner=other_membership, name="UnseededClubChar",
            char_class="Some Class", class_option=None,
        )

        from django.apps import apps
        with connection.schema_editor() as schema_editor:
            run_migration(apps, schema_editor)

        seeded_char = Character.objects.get(name="SeededClubChar")
        unseeded_char = Character.objects.get(name="UnseededClubChar")

        assert seeded_char.class_option_id is not None
        assert seeded_char.class_option.name == class_name_seeded

        assert unseeded_char.class_option_id is None
        assert unseeded_char.char_class == "Some Class"