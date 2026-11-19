"""End-to-end integration tests for the full starting equipment claim flow."""

import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentTemplate,
)

pytestmark = [pytest.mark.django_db]


def create_url(club):
    return reverse("characters:create", kwargs={"club_slug": club.slug})


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def claim_url(club, character):
    return reverse(
        "starting_equipment:claim",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


def _create_template_with_entries(club):
    """Create an active template with class/background entries and items."""
    template = StartingEquipmentTemplate.objects.create(
        club=club, name="Active Template", is_active=True
    )

    # Class entry for Fighter
    class_entry = StartingEquipmentClassEntry.objects.create(
        template=template, char_class="Fighter", min_level=1, max_level=20, coins_cp=1000
    )

    # Class item
    longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
    StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=longsword, quantity=1, is_choice=False
    )

    # Background entry for Acolyte
    bg_entry = StartingEquipmentBackgroundEntry.objects.create(
        template=template, background="Acolyte", coins_cp=500
    )

    # Background item
    holy_symbol = Item.objects.create(club=club, name="Holy Symbol", value_cp=500)
    StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry, item=holy_symbol, quantity=1, is_choice=False
    )

    # Level coins for level 5
    StartingEquipmentLevelCoins.objects.create(template=template, level=5, coins_cp=5000)

    return template


class TestFullClaimFlow:
    """Tests covering the full claim flow: create character -> activate template -> claim."""

    def test_claim_flow_from_character_creation(self, club, login, player, character):
        """
        Full E2E flow:
        1. Create character without active template -> no ledger entry, claimed=False
        2. Create active template with class/background entries
        3. Visit character detail -> claim button appears (can_claim=True)
        4. POST claim -> ledger entry created with items/coins, claimed=True
        5. Visit character detail -> claim button gone (can_claim=False)
        """
        client = login(player)

        # 1. Create character without active template
        response = client.post(
            create_url(club),
            {"name": "Test Character", "char_class": "Fighter", "background": "Acolyte"},
        )
        assert response.status_code == 302

        character = Character.objects.get(name="Test Character")
        character.refresh_from_db()

        # Verify no ledger entry and claimed flag is False
        assert LedgerEntry.objects.filter(character=character).count() == 0
        assert character.starting_equipment_claimed is False

        # 2. Create active template with class/background entries
        template = _create_template_with_entries(club)
        assert template.is_active is True

        # 3. Visit character detail -> claim button should appear
        response = client.get(detail_url(club, character))
        assert response.status_code == 200
        assert response.context["can_claim_starting_equipment"] is True

        # 4. POST claim (HTMX) -> ledger entry created, claimed=True
        response = client.post(claim_url(club, character), HTTP_HX_REQUEST="true")
        assert response.status_code == 204

        character.refresh_from_db()
        assert character.starting_equipment_claimed is True

        # Verify ledger entry created with class/background items and coins
        entries = LedgerEntry.objects.filter(character=character)
        assert entries.count() == 1
        entry = entries.first()
        assert entry.kind == LedgerEntry.Kind.AWARD
        assert entry.note == "Starting equipment"
        assert entry.created_by == player

        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]
        assert {line.item.name for line in item_lines} == {"Longsword", "Holy Symbol"}
        coin_lines = [line for line in lines if line.coins != 0]
        assert sum(line.coins for line in coin_lines) == 1500  # 1000 class + 500 background

        # 5. Visit character detail -> claim button no longer appears
        response = client.get(detail_url(club, character))
        assert response.status_code == 200
        assert response.context["can_claim_starting_equipment"] is False


class TestAutoApplyOnCreation:
    """Tests that auto-apply on character creation sets starting_equipment_claimed=True."""

    def test_auto_apply_on_creation_sets_claimed_flag(self, club, login, player):
        """
        Create character WITH active template -> ledger entry created AND claimed=True.
        """
        # Create active template first
        _create_template_with_entries(club)

        client = login(player)

        # Create character with class/background matching template
        response = client.post(
            create_url(club),
            {"name": "Auto Claim Character", "char_class": "Fighter", "background": "Acolyte"},
        )
        assert response.status_code == 302

        character = Character.objects.get(name="Auto Claim Character")
        character.refresh_from_db()

        # Verify ledger entry created
        entries = LedgerEntry.objects.filter(character=character)
        assert entries.count() == 1
        entry = entries.first()
        assert entry.kind == LedgerEntry.Kind.AWARD
        assert entry.note == "Starting equipment"

        # Verify claimed flag is True (this is the fix being tested)
        assert character.starting_equipment_claimed is True


class TestClaimNoMatch:
    """Tests edge case: claim when template has no matching class/background."""

    def test_claim_with_no_matching_entries_still_marks_claimed(self, club, login, player):
        """
        Claim with template that has no matching class/background
        -> should still mark claimed=True to prevent retry loops.
        """
        # Create template with NO matching entries for our character
        template = StartingEquipmentTemplate.objects.create(
            club=club, name="Mismatched Template", is_active=True
        )
        # Add entry for Wizard (not Fighter)
        StartingEquipmentClassEntry.objects.create(
            template=template, char_class="Wizard", min_level=1, max_level=20, coins_cp=1000
        )

        # Create character with Fighter class (no matching template entry)
        client = login(player)
        response = client.post(
            create_url(club),
            {"name": "Mismatch Character", "char_class": "Fighter", "background": "Acolyte"},
        )
        assert response.status_code == 302

        character = Character.objects.get(name="Mismatch Character")
        character.refresh_from_db()
        assert character.starting_equipment_claimed is False  # Not auto-applied

        # POST claim -> should still mark claimed=True even though nothing granted
        response = client.post(claim_url(club, character), HTTP_HX_REQUEST="true")
        assert response.status_code == 204

        character.refresh_from_db()
        assert character.starting_equipment_claimed is True

        # No ledger entry should be created (nothing to grant)
        assert LedgerEntry.objects.filter(character=character).count() == 0
