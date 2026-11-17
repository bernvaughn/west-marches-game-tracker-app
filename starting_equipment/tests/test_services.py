"""Tests for apply_starting_equipment service."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Membership
from ledger.models import LedgerEntry
from player_characters.models import Character
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentClassLine,
    StartingEquipmentRequest,
)

# Import the service function (will be created by SE3)
# from starting_equipment.services import apply_starting_equipment

pytestmark = [pytest.mark.django_db]

User = get_user_model()


class TestApplyStartingEquipment:
    """Tests for the apply_starting_equipment service function."""

    def test_class_match_case_insensitive(
        self,
        character_lowercase_class_bg,
        template,
        class_entry,
        class_line,
        game_master_user,
    ):
        """Class equipment match is case-insensitive (char_class 'fighter' matches
        template 'Fighter')."""
        # Import here to avoid circular import if service doesn't exist yet
        from starting_equipment.services import apply_starting_equipment

        # Character has char_class="fighter" (lowercase), template has "Fighter"
        entry = apply_starting_equipment(
            character_lowercase_class_bg, template, game_master_user
        )

        assert entry is not None
        assert entry.kind == "award"
        assert entry.note == "Starting equipment"
        assert entry.created_by == game_master_user

        # Verify the class item was granted
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]
        assert len(item_lines) == 1
        assert item_lines[0].item.name == "Longsword"
        assert item_lines[0].quantity == 1

    def test_background_match_case_insensitive(
        self,
        character_lowercase_class_bg,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        game_master_user,
    ):
        """Background equipment match is case-insensitive (background 'acolyte'
        matches template 'Acolyte')."""
        from starting_equipment.services import apply_starting_equipment

        # Character has background="acolyte" (lowercase), template has "Acolyte"
        entry = apply_starting_equipment(
            character_lowercase_class_bg, template, game_master_user
        )

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]

        # Should have both class item and background item
        assert len(item_lines) == 2
        item_names = {line.item.name for line in item_lines}
        assert "Longsword" in item_names
        assert "Holy Symbol" in item_names

    def test_level_coins_applied_for_level_gt_1(
        self,
        character_level_5,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        level_coins,
        game_master_user,
    ):
        """Level coins applied for character level > 1 from LevelCoins table."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_level_5, template, game_master_user)

        assert entry is not None
        lines = entry.lines.all()

        # Should have class item, background item, class coins, background coins, AND level coins
        coin_lines = [line for line in lines if line.coins != 0]
        item_lines = [line for line in lines if line.item is not None]

        assert len(item_lines) == 2  # Longsword + Holy Symbol

        # Check coins: class (1000) + background (500) + level (5000) = 6500
        total_coins = sum(line.coins for line in coin_lines)
        assert total_coins == 6500

    def test_level_1_character_no_level_coins(
        self,
        character_with_class_bg,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        level_coins,
        game_master_user,
    ):
        """Level 1 character does NOT get level coins."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_with_class_bg, template, game_master_user)

        assert entry is not None
        lines = entry.lines.all()
        coin_lines = [line for line in lines if line.coins != 0]

        # Should only have class (1000) + background (500) = 1500 coins
        total_coins = sum(line.coins for line in coin_lines)
        assert total_coins == 1500

    def test_only_approved_magic_requests_granted(
        self,
        character_with_class_bg,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        magic_option,
        approved_request,
        pending_request,
        declined_request,
        game_master_user,
    ):
        """Only approved magic item requests are granted (pending/declined ignored)."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_with_class_bg, template, game_master_user)

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]

        # Should have class item, background item, AND approved magic item
        # NOT pending or declined magic items
        assert len(item_lines) == 3
        item_names = {line.item.name for line in item_lines}
        assert "Longsword" in item_names
        assert "Holy Symbol" in item_names
        assert "Potion of Healing" in item_names
        assert "Scroll of Fireball" not in item_names

    def test_empty_template_returns_none(
        self, character_with_class_bg, empty_template, game_master_user
    ):
        """Empty template (no class/background/level entries) returns None."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_with_class_bg, empty_template, game_master_user)

        assert entry is None
        # No ledger entry should be created
        assert LedgerEntry.objects.count() == 0

    def test_single_ledger_entry_with_all_granted_items_and_coins(
        self,
        character_level_5,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        level_coins,
        magic_option,
        game_master_user,
    ):
        """Service creates single ledger entry with all granted items and coins."""
        from starting_equipment.services import apply_starting_equipment
        from starting_equipment.models import StartingEquipmentRequest

        # Create an approved request for this specific character
        StartingEquipmentRequest.objects.create(
            club=character_level_5.club,
            character=character_level_5,
            item=magic_option.item,
            quantity=1,
            status=StartingEquipmentRequest.Status.APPROVED,
        )

        entry = apply_starting_equipment(character_level_5, template, game_master_user)

        assert entry is not None
        # Verify it's a single entry (not multiple)
        assert LedgerEntry.objects.count() == 1

        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]
        coin_lines = [line for line in lines if line.coins != 0]

        # Items: Longsword (class) + Holy Symbol (bg) + Potion of Healing (approved request)
        assert len(item_lines) == 3

        # Coins: class (1000) + background (500) + level (5000) = 6500
        total_coins = sum(line.coins for line in coin_lines)
        assert total_coins == 6500

    def test_uses_ledger_record_with_award_and_note(
        self, character_with_class_bg, template, class_entry, class_line, game_master_user
    ):
        """Service uses ledger.record() with kind='award' and note='Starting equipment'."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_with_class_bg, template, game_master_user)

        assert entry is not None
        assert entry.kind == LedgerEntry.Kind.AWARD
        assert entry.note == "Starting equipment"
        assert entry.created_by == game_master_user

    def test_class_entry_level_range_respected_min_level(
        self,
        character_level_3_wizard,
        template,
        class_entry_limited_level,
        class_item,
        game_master_user,
    ):
        """Class entry level range (min_level) is respected - level 3 wizard below
        min_level=5."""
        from starting_equipment.services import apply_starting_equipment

        # Add a class line for the wizard entry
        StartingEquipmentClassLine.objects.create(
            class_entry=class_entry_limited_level, item=class_item, quantity=1, is_choice=False
        )

        entry = apply_starting_equipment(character_level_3_wizard, template, game_master_user)

        # Character is level 3, class entry is for levels 5-10
        # Should NOT grant class equipment (no matching class entry for level 3)
        # Also no background entry for "Sage" in this template
        assert entry is None
        assert LedgerEntry.objects.count() == 0

    def test_class_entry_level_range_respected_max_level(
        self,
        character_level_7_wizard,
        template,
        class_entry_limited_level,
        class_item,
        game_master_user,
    ):
        """Class entry level range (max_level) is respected - level 7 wizard inside
        range 5-10."""
        from starting_equipment.services import apply_starting_equipment

        StartingEquipmentClassLine.objects.create(
            class_entry=class_entry_limited_level, item=class_item, quantity=1, is_choice=False
        )

        entry = apply_starting_equipment(character_level_7_wizard, template, game_master_user)

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]
        # Should grant class item (level 7 is within 5-10)
        assert len(item_lines) == 1
        assert item_lines[0].item.name == "Longsword"

    def test_choice_groups_skipped_in_class_lines(
        self,
        character_with_class_bg,
        template,
        class_entry,
        class_line,
        class_line_choice,
        game_master_user,
    ):
        """Choice groups in class lines are skipped (is_choice=True)."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_with_class_bg, template, game_master_user)

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]

        # Should only get the non-choice item (Longsword), not the choice item (Chain Mail)
        assert len(item_lines) == 1
        assert item_lines[0].item.name == "Longsword"
        assert "Chain Mail" not in [line.item.name for line in item_lines]

    def test_choice_groups_skipped_in_background_lines(
        self, character_with_class_bg, template, class_entry, class_line, bg_entry, bg_line, bg_line_choice, game_master_user
    ):
        """Choice groups in background lines are skipped (is_choice=True)."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_with_class_bg, template, game_master_user)

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]

        # Should only get the non-choice background item
        # (Holy Symbol) - but also class item (Longsword)
        assert len(item_lines) == 2
        item_names = {line.item.name for line in item_lines}
        assert "Longsword" in item_names
        assert "Holy Symbol" in item_names

    def test_background_equipment_only_when_character_has_background(
        self,
        character_no_bg,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        game_master_user,
    ):
        """Background equipment only applied when character.background is set."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_no_bg, template, game_master_user)

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]

        # Should only get class item (Longsword), no background item
        assert len(item_lines) == 1
        assert item_lines[0].item.name == "Longsword"

    def test_no_class_equipment_when_character_has_no_class(
        self,
        character_no_class,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        game_master_user,
    ):
        """Class equipment not granted when character has no class."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_no_class, template, game_master_user)

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]

        # Should only get background item (Holy Symbol), no class item
        assert len(item_lines) == 1
        assert item_lines[0].item.name == "Holy Symbol"

    def test_character_level_none_defaults_to_1(
        self, club, player, template, class_entry, class_line, bg_entry, game_master_user
    ):
        """Character with level=None defaults to level 1 (no level coins)."""
        from starting_equipment.services import apply_starting_equipment

        owner = Membership.objects.get(user=player, club=club)
        character = Character.objects.create(
            club=club,
            owner=owner,
            name="No Level",
            char_class="Fighter",
            background="Acolyte",
            level=None,  # Explicitly None
        )

        entry = apply_starting_equipment(character, template, game_master_user)

        assert entry is not None
        lines = entry.lines.all()
        coin_lines = [line for line in lines if line.coins != 0]
        total_coins = sum(line.coins for line in coin_lines)
        # Should only get class + background coins, no level coins
        assert total_coins == 1500

    def test_multiple_approved_requests_all_granted(
        self,
        character_with_class_bg,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        magic_option,
        magic_item_2,
        game_master_user,
    ):
        """Multiple approved magic item requests are all granted."""
        from starting_equipment.services import apply_starting_equipment

        # Create a second magic option
        MagicItemStartingOption.objects.create(
            template=template, item=magic_item_2, max_per_character=1
        )

        # Create two approved requests
        StartingEquipmentRequest.objects.create(
            club=character_with_class_bg.club,
            character=character_with_class_bg,
            item=magic_option.item,
            quantity=1,
            status=StartingEquipmentRequest.Status.APPROVED,
        )
        StartingEquipmentRequest.objects.create(
            club=character_with_class_bg.club,
            character=character_with_class_bg,
            item=magic_item_2,
            quantity=2,
            status=StartingEquipmentRequest.Status.APPROVED,
        )

        entry = apply_starting_equipment(character_with_class_bg, template, game_master_user)

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]

        # Class + background + 2 magic items = 4 items
        assert len(item_lines) == 4
        item_names = {line.item.name for line in item_lines}
        assert "Longsword" in item_names
        assert "Holy Symbol" in item_names
        assert "Potion of Healing" in item_names
        assert "Scroll of Fireball" in item_names

        # Check quantities
        for item_line in item_lines:
            if item_line.item.name == "Scroll of Fireball":
                assert item_line.quantity == 2

    def test_inactive_template_still_works(
        self, character_with_class_bg, inactive_template, class_entry, class_line, game_master_user
    ):
        """Inactive template still works (is_active not checked in service)."""
        from starting_equipment.services import apply_starting_equipment

        # Move class entry to inactive template
        class_entry.template = inactive_template
        class_entry.save()

        entry = apply_starting_equipment(
            character_with_class_bg, inactive_template, game_master_user
        )

        assert entry is not None
        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]
        assert len(item_lines) == 1
        assert item_lines[0].item.name == "Longsword"

    def test_class_coins_included(
        self, character_no_bg, template, class_entry, class_line, game_master_user
    ):
        """Class entry coins_cp is included in ledger."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_no_bg, template, game_master_user)

        assert entry is not None
        lines = entry.lines.all()
        coin_lines = [line for line in lines if line.coins != 0]
        # class_entry.coins_cp = 1000
        total_coins = sum(line.coins for line in coin_lines)
        assert total_coins == 1000

    def test_background_coins_included(
        self,
        character_with_class_bg,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        game_master_user,
    ):
        """Background entry coins_cp is included in ledger."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_with_class_bg, template, game_master_user)

        assert entry is not None
        lines = entry.lines.all()
        coin_lines = [line for line in lines if line.coins != 0]
        # class_entry.coins_cp = 1000 + bg_entry.coins_cp = 500
        total_coins = sum(line.coins for line in coin_lines)
        assert total_coins == 1500

    def test_level_coins_at_different_levels(
        self,
        character_level_10,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        level_coins_lvl_10,
        game_master_user,
    ):
        """Level coins at level 10 uses correct LevelCoins entry."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_level_10, template, game_master_user)

        assert entry is not None
        lines = entry.lines.all()
        coin_lines = [line for line in lines if line.coins != 0]
        # class (1000) + bg (500) + level 10 (15000) = 16500
        total_coins = sum(line.coins for line in coin_lines)
        assert total_coins == 16500

    def test_no_level_coins_entry_for_level_no_coins_granted(
        self,
        character_level_5,
        template,
        class_entry,
        class_line,
        bg_entry,
        bg_line,
        game_master_user,
    ):
        """If no LevelCoins entry exists for character's level, no level coins granted."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_level_5, template, game_master_user)

        assert entry is not None
        lines = entry.lines.all()
        coin_lines = [line for line in lines if line.coins != 0]
        # Only class + bg coins, no level coins (no LevelCoins entry for level 5)
        total_coins = sum(line.coins for line in coin_lines)
        assert total_coins == 1500

    def test_actor_can_be_none(
        self, character_with_class_bg, template, class_entry, class_line
    ):
        """Actor can be None (no user specified)."""
        from starting_equipment.services import apply_starting_equipment

        entry = apply_starting_equipment(character_with_class_bg, template, None)

        assert entry is not None
        assert entry.created_by is None

    def test_character_from_different_club_raises_error(
        self, other_club, template, class_entry, class_line, game_master_user
    ):
        """Character from different club than template should not match entries (club scoping)."""
        from accounts.models import Membership, User
        from starting_equipment.services import apply_starting_equipment

        # Create a user and membership for other_club
        other_club_user = User.objects.create_user(
            "other_club@test.com", password="pw", display_name="Other Club User"
        )
        owner = Membership.objects.create(user=other_club_user, club=other_club)
        character = Character.objects.create(
            club=other_club,
            owner=owner,
            name="Other Club Fighter",
            char_class="Fighter",
            background="Acolyte",
            level=1,
        )

        # Template is for club, character is for other_club
        # The club-scoped managers should prevent cross-club access
        entry = apply_starting_equipment(character, template, game_master_user)

        # Should return None because no matching entries found (club scoping)
        assert entry is None