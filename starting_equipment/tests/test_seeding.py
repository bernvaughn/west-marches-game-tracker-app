"""Tests for the starting equipment seeding service."""

import pytest

from items.models import Item
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentTemplate,
)
from starting_equipment.seeding import (
    DEFAULT_TEMPLATE_NAME,
    SeedSummary,
    StartingEquipmentSeedError,
    seed_default_starting_equipment,
)


@pytest.mark.django_db
class TestSeedDefaultStartingEquipment:
    """Tests for seed_default_starting_equipment service function."""

    def test_first_run_creates_everything(self, club):
        """First run creates template, items, entries, and level coins."""
        summary = seed_default_starting_equipment(club)

        # Check summary
        assert summary.template_created is True
        assert summary.skipped is False
        assert summary.items_created > 0
        assert summary.class_entries_created > 0
        assert summary.class_entries_updated == 0
        assert summary.background_entries_created > 0
        assert summary.background_entries_updated == 0
        assert summary.level_coins_created > 0
        assert summary.level_coins_updated == 0

        # Check template
        template = StartingEquipmentTemplate.objects.get(club=club, name=DEFAULT_TEMPLATE_NAME)
        assert template.is_active is True
        expected_desc = (
            "Default starting equipment per 2024 D&D Player's Handbook and Dungeon Master's Guide."
        )
        assert template.description == expected_desc

        # Check class entries - one per CLASS_EQUIPMENT key
        from starting_equipment.seeding import CLASS_EQUIPMENT

        class_entries = StartingEquipmentClassEntry.objects.for_club(club).all()
        assert class_entries.count() == len(CLASS_EQUIPMENT)
        assert len(CLASS_EQUIPMENT) == 12
        for class_name in CLASS_EQUIPMENT:
            entry = class_entries.get(class_option__name=class_name)
            assert entry.coins_cp == CLASS_EQUIPMENT[class_name]["coins_cp"]
            assert entry.min_level == 1
            assert entry.max_level == 20
            # Check lines exist for this class
            lines = entry.lines.all()
            assert lines.count() == len(CLASS_EQUIPMENT[class_name]["items"])

        # Check background entries - one per BACKGROUND_EQUIPMENT key
        from starting_equipment.seeding import BACKGROUND_EQUIPMENT

        bg_entries = StartingEquipmentBackgroundEntry.objects.for_club(club).all()
        assert bg_entries.count() == len(BACKGROUND_EQUIPMENT)
        for bg_name in BACKGROUND_EQUIPMENT:
            entry = bg_entries.get(background_option__name=bg_name)
            assert entry.coins_cp == BACKGROUND_EQUIPMENT[bg_name]["coins_cp"]
            lines = entry.lines.all()
            assert lines.count() == len(BACKGROUND_EQUIPMENT[bg_name]["items"])

        # Check level coins - one per LEVEL_COINS_CP key
        from starting_equipment.seeding import LEVEL_COINS_CP

        level_coins = StartingEquipmentLevelCoins.objects.for_club(club).all()
        assert level_coins.count() == len(LEVEL_COINS_CP)
        for level, coins_cp in LEVEL_COINS_CP.items():
            lc = level_coins.get(level=level)
            assert lc.coins_cp == coins_cp

        # Check items were created
        # Count unique items across class and background equipment
        expected_items = set()
        for class_data in CLASS_EQUIPMENT.values():
            for item_data in class_data["items"]:
                expected_items.add(item_data[0])
        for bg_data in BACKGROUND_EQUIPMENT.values():
            for item_data in bg_data["items"]:
                expected_items.add(item_data[0])
        items = Item.objects.for_club(club).all()
        assert items.count() == len(expected_items)

    def test_second_run_skipped_when_not_forced(self, club):
        """Second run without force returns skipped=True and creates nothing."""
        # First run
        summary1 = seed_default_starting_equipment(club)
        assert summary1.template_created is True

        # Record counts after first run
        template_count = StartingEquipmentTemplate.objects.for_club(club).count()
        class_entry_count = StartingEquipmentClassEntry.objects.for_club(club).count()
        bg_entry_count = StartingEquipmentBackgroundEntry.objects.for_club(club).count()
        class_line_count = StartingEquipmentClassLine.objects.for_club(club).count()
        bg_line_count = StartingEquipmentBackgroundLine.objects.for_club(club).count()
        level_coins_count = StartingEquipmentLevelCoins.objects.for_club(club).count()
        item_count = Item.objects.for_club(club).count()

        # Second run
        summary2 = seed_default_starting_equipment(club)

        # Check summary
        assert summary2.template_created is False
        assert summary2.skipped is True
        assert summary2.items_created == 0
        assert summary2.class_entries_created == 0
        assert summary2.class_entries_updated == 0
        assert summary2.background_entries_created == 0
        assert summary2.background_entries_updated == 0
        assert summary2.level_coins_created == 0
        assert summary2.level_coins_updated == 0

        # Check counts unchanged
        assert StartingEquipmentTemplate.objects.for_club(club).count() == template_count
        assert StartingEquipmentClassEntry.objects.for_club(club).count() == class_entry_count
        assert StartingEquipmentBackgroundEntry.objects.for_club(club).count() == bg_entry_count
        assert StartingEquipmentClassLine.objects.for_club(club).count() == class_line_count
        assert StartingEquipmentBackgroundLine.objects.for_club(club).count() == bg_line_count
        assert StartingEquipmentLevelCoins.objects.for_club(club).count() == level_coins_count
        assert Item.objects.for_club(club).count() == item_count

    def test_edited_item_untouched_on_rerun(self, club):
        """Pre-existing edited item is not modified on rerun without force."""
        # First run
        seed_default_starting_equipment(club)

        # Edit an item
        item = Item.objects.for_club(club).get(name="Greataxe")
        item.value_cp = 9999
        item.symbol = "⚔️"
        item.save()

        # Second run without force
        summary = seed_default_starting_equipment(club)
        assert summary.skipped is True

        # Item should be unchanged
        item.refresh_from_db()
        assert item.value_cp == 9999
        assert item.symbol == "⚔️"

    def test_edited_item_untouched_with_fresh_template(self, club):
        """Edited item is not modified when creating a fresh template with force=True."""
        # First run
        seed_default_starting_equipment(club)

        # Edit an item
        item = Item.objects.for_club(club).get(name="Greataxe")
        item.value_cp = 9999
        item.symbol = "⚔️"
        item.save()

        # Create a NEW template with force=True (should not affect items)
        summary = seed_default_starting_equipment(club, name="Fresh Template", force=True)
        assert summary.template_created is True
        assert summary.skipped is False

        # Item should be unchanged (get_or_create never updates items)
        item.refresh_from_db()
        assert item.value_cp == 9999
        assert item.symbol == "⚔️"

    def test_force_updates_entries(self, club):
        """force=True updates existing entries and lines."""
        # First run
        seed_default_starting_equipment(club)

        # Modify some entries
        StartingEquipmentTemplate.objects.get(club=club, name=DEFAULT_TEMPLATE_NAME)

        # Change class entry coins
        fighter_entry = StartingEquipmentClassEntry.objects.for_club(club).get(class_option__name="Fighter")
        fighter_entry.coins_cp = 999
        fighter_entry.save()

        # Change a line quantity
        longsword_line = (
            StartingEquipmentClassLine.objects.for_club(club)
            .filter(class_entry=fighter_entry, item__name="Longsword")
            .first()
        )
        longsword_line.quantity = 5
        longsword_line.save()

        # Change level coins
        lc = StartingEquipmentLevelCoins.objects.for_club(club).get(level=5)
        lc.coins_cp = 12345
        lc.save()

        # Run with force=True
        summary = seed_default_starting_equipment(club, force=True)

        # Check updated counts
        assert summary.template_created is False
        assert summary.skipped is False
        assert summary.class_entries_updated > 0
        assert summary.level_coins_updated > 0

        # Verify values restored
        fighter_entry.refresh_from_db()
        assert fighter_entry.coins_cp == 500  # Original value from CLASS_EQUIPMENT

        longsword_line.refresh_from_db()
        assert longsword_line.quantity == 1  # Original value

        lc.refresh_from_db()
        assert lc.coins_cp == 50000  # Original value from LEVEL_COINS_CP

        # No new rows created
        assert StartingEquipmentClassEntry.objects.for_club(club).count() == 12  # 12 classes
        assert StartingEquipmentLevelCoins.objects.for_club(club).count() == 19  # levels 2-20

    def test_duplicate_items_raises_error(self, club):
        """Duplicate item names raise StartingEquipmentSeedError."""
        # First run to create items
        seed_default_starting_equipment(club)

        # Create a duplicate item manually
        Item.objects.create(
            club=club,
            name="Greataxe",  # Already exists
            value_cp=100,
            symbol="⚔️",
        )

        # Should raise error
        with pytest.raises(StartingEquipmentSeedError) as exc_info:
            seed_default_starting_equipment(club, name="New Template", force=True)

        assert "Multiple items named 'Greataxe'" in str(exc_info.value)

        # Nothing committed for the new template (atomic)
        assert (
            StartingEquipmentTemplate.objects.for_club(club).filter(name="New Template").count()
            == 0
        )

    def test_club_isolation(self, club, other_club):
        """Seeding club A creates no rows for club B."""
        # Seed club A
        seed_default_starting_equipment(club)

        # Check club B has nothing
        assert StartingEquipmentTemplate.objects.for_club(other_club).count() == 0
        assert Item.objects.for_club(other_club).count() == 0
        assert StartingEquipmentClassEntry.objects.for_club(other_club).count() == 0
        assert StartingEquipmentBackgroundEntry.objects.for_club(other_club).count() == 0
        assert StartingEquipmentLevelCoins.objects.for_club(other_club).count() == 0

    def test_custom_name_creates_second_template(self, club):
        """Custom name creates a second template with its own entries."""
        # First template
        summary1 = seed_default_starting_equipment(club, name="First Template")
        assert summary1.template_created is True

        # Second template with custom name
        summary2 = seed_default_starting_equipment(club, name="Second Template")
        assert summary2.template_created is True
        assert summary2.skipped is False

        # Both templates exist
        templates = StartingEquipmentTemplate.objects.for_club(club).all()
        assert templates.count() == 2
        names = {t.name for t in templates}
        assert "First Template" in names
        assert "Second Template" in names

        # Second template has its own entries
        t2 = templates.get(name="Second Template")
        class_entries = t2.class_entries.all()
        assert class_entries.count() == 12  # All classes

    def test_seed_summary_fields(self, club):
        """SeedSummary contains all expected fields with correct types."""
        summary = seed_default_starting_equipment(club)

        assert isinstance(summary, SeedSummary)
        assert isinstance(summary.template_created, bool)
        assert isinstance(summary.skipped, bool)
        assert isinstance(summary.items_created, int)
        assert isinstance(summary.class_entries_created, int)
        assert isinstance(summary.class_entries_updated, int)
        assert isinstance(summary.background_entries_created, int)
        assert isinstance(summary.background_entries_updated, int)
        assert isinstance(summary.level_coins_created, int)
        assert isinstance(summary.level_coins_updated, int)

    def test_force_updates_background_entries(self, club):
        """force=True updates background entry coins and lines."""
        seed_default_starting_equipment(club)

        # Modify background entry
        StartingEquipmentTemplate.objects.get(club=club, name=DEFAULT_TEMPLATE_NAME)
        acolyte = StartingEquipmentBackgroundEntry.objects.for_club(club).get(background_option__name="Acolyte")
        acolyte.coins_cp = 999
        acolyte.save()

        # Modify a line
        holy_symbol_line = (
            StartingEquipmentBackgroundLine.objects.for_club(club)
            .filter(background_entry=acolyte, item__name="Holy Symbol (Amulet)")
            .first()
        )
        holy_symbol_line.quantity = 5
        holy_symbol_line.save()

        # Run with force
        summary = seed_default_starting_equipment(club, force=True)

        assert summary.background_entries_updated > 0

        acolyte.refresh_from_db()
        assert acolyte.coins_cp == 1500  # Original

        holy_symbol_line.refresh_from_db()
        assert holy_symbol_line.quantity == 1  # Original

    def test_force_updates_level_coins(self, club):
        """force=True updates level coins."""
        seed_default_starting_equipment(club)

        # Modify level coins
        lc = StartingEquipmentLevelCoins.objects.for_club(club).get(level=10)
        lc.coins_cp = 99999
        lc.save()

        # Run with force
        summary = seed_default_starting_equipment(club, force=True)

        assert summary.level_coins_updated > 0

        lc.refresh_from_db()
        assert lc.coins_cp == 50000  # Original
