"""Tests for the seed_starting_equipment management command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import Club
from items.models import Item
from starting_equipment.models import (
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentTemplate,
)
from starting_equipment.seeding import LEVEL_COINS_CP


@pytest.mark.django_db
class TestSeedStartingEquipmentCommand:
    """Tests for the seed_starting_equipment management command."""

    def test_fresh_club_output(self, club):
        """Output for --club slug on a fresh club."""
        out = StringIO()
        call_command("seed_starting_equipment", "--club", club.slug, stdout=out)

        output = out.getvalue()
        # "Using club:" only appears when --club is NOT specified
        assert "Using club:" not in output
        assert "Created template: 2024 D&D Default" in output
        assert "Created" in output and "new items" in output
        assert "Class entries: 12 created, 0 updated" in output
        assert "Background entries: 16 created, 0 updated" in output
        assert f"Level coins: {len(LEVEL_COINS_CP)} created, 0 updated" in output
        assert "Successfully seeded '2024 D&D Default' template" in output

        # Verify template was created
        template = StartingEquipmentTemplate.objects.get(club=club, name="2024 D&D Default")
        assert template.is_active is True

    def test_rerun_prints_warning(self, club):
        """Rerun without --force prints warning and returns early."""
        # First run
        out1 = StringIO()
        call_command("seed_starting_equipment", "--club", club.slug, stdout=out1)

        # Second run
        out2 = StringIO()
        call_command("seed_starting_equipment", "--club", club.slug, stdout=out2)

        output = out2.getvalue()
        assert "Template exists: 2024 D&D Default" in output
        assert "Template already exists. Use --force to update entries." in output
        # Should not have created/updated lines
        assert "Class entries:" not in output
        assert "Background entries:" not in output
        assert "Level coins:" not in output
        assert "Successfully seeded" not in output

    def test_force_prints_updated_lines(self, club):
        """--force prints updated lines."""
        # First run
        call_command("seed_starting_equipment", "--club", club.slug)

        # Modify an entry
        StartingEquipmentTemplate.objects.get(club=club, name="2024 D&D Default")
        fighter = StartingEquipmentClassEntry.objects.for_club(club).get(
            class_option__name="Fighter"
        )
        fighter.coins_cp = 999
        fighter.save()

        # Modify a line
        longsword = (
            StartingEquipmentClassLine.objects.for_club(club)
            .filter(class_entry=fighter, item__name="Longsword")
            .first()
        )
        longsword.quantity = 5
        longsword.save()

        # Modify level coins
        lc = StartingEquipmentLevelCoins.objects.for_club(club).get(level=5)
        lc.coins_cp = 12345
        lc.save()

        # Run with --force
        out = StringIO()
        call_command("seed_starting_equipment", "--club", club.slug, "--force", stdout=out)

        output = out.getvalue()
        assert "Template exists: 2024 D&D Default" in output
        # force=True updates ALL entries to match defaults
        assert "Class entries: 0 created, 12 updated" in output
        assert "Background entries: 0 created, 16 updated" in output
        assert "Level coins: 0 created, 19 updated" in output
        assert "Successfully seeded '2024 D&D Default' template" in output

        # Verify values restored
        fighter.refresh_from_db()
        assert fighter.coins_cp == 500
        longsword.refresh_from_db()
        assert longsword.quantity == 1
        lc.refresh_from_db()
        assert lc.coins_cp == 50000

    def test_unknown_slug_raises_command_error(self):
        """Unknown club slug raises CommandError."""
        with pytest.raises(CommandError) as exc_info:
            call_command("seed_starting_equipment", "--club", "nonexistent")

        assert "Club with slug 'nonexistent' does not exist." in str(exc_info.value)

    def test_duplicate_items_raises_command_error(self, club):
        """Duplicate items raise CommandError."""
        # First run
        call_command("seed_starting_equipment", "--club", club.slug)

        # Create duplicate item
        Item.objects.create(
            club=club,
            name="Greataxe",  # Already exists
            value_cp=100,
            symbol="⚔️",
        )

        # Should raise CommandError
        with pytest.raises(CommandError) as exc_info:
            call_command(
                "seed_starting_equipment",
                "--club",
                club.slug,
                "--name",
                "New Template",
                "--force",
            )

        assert "Multiple items named 'Greataxe'" in str(exc_info.value)

    def test_custom_name_flag(self, club):
        """Custom --name creates template with that name."""
        out = StringIO()
        call_command(
            "seed_starting_equipment",
            "--club",
            club.slug,
            "--name",
            "Custom Template",
            stdout=out,
        )

        output = out.getvalue()
        assert "Created template: Custom Template" in output
        assert "Successfully seeded 'Custom Template' template" in output

        template = StartingEquipmentTemplate.objects.get(club=club, name="Custom Template")
        assert template.name == "Custom Template"

    def test_default_club_when_no_club_specified(self, club):
        """Uses first club when --club not specified."""
        out = StringIO()
        call_command("seed_starting_equipment", stdout=out)

        output = out.getvalue()
        assert f"Using club: {club.name} ({club.slug})" in output
        assert "Created template: 2024 D&D Default" in output

    def test_no_clubs_raises_error(self):
        """Raises error when no clubs exist and --club not specified."""
        Club.objects.all().delete()

        with pytest.raises(CommandError) as exc_info:
            call_command("seed_starting_equipment")

        assert "No clubs exist. Create a club first or specify --club." in str(exc_info.value)
