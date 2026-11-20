"""End-to-end integration tests for the full starting equipment claim flow."""

import pytest
from django.urls import reverse

from character_options.models import Background, CharacterClass
from items.models import Item
from ledger.models import LedgerEntry
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentRequest,
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

    # Create class and background options (seeded by the club fixture)
    fighter_class = CharacterClass.objects.get(club=club, name="Fighter")
    acolyte_bg = Background.objects.get(club=club, name="Acolyte")

    # Class entry for Fighter
    class_entry = StartingEquipmentClassEntry.objects.create(
        template=template,
        class_option=fighter_class,
        min_level=1,
        max_level=20,
        coins_cp=1000,
    )

    # Class item
    longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
    StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=longsword, quantity=1, is_choice=False
    )

    # Background entry for Acolyte
    bg_entry = StartingEquipmentBackgroundEntry.objects.create(
        template=template,
        background_option=acolyte_bg,
        coins_cp=500,
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

        # Need to set the FKs on the character for matching to work
        fighter_class = CharacterClass.objects.get(club=club, name="Fighter")
        acolyte_bg = Background.objects.get(club=club, name="Acolyte")
        character.class_option = fighter_class
        character.background_option = acolyte_bg
        character.save(update_fields=["class_option", "background_option"])

        # 3. Visit character detail -> claim button should appear
        response = client.get(detail_url(club, character))
        assert response.status_code == 200
        assert response.context["can_claim_starting_equipment"] is True

        # 4. POST claim (HTMX) -> ledger entry created with items/coins, claimed=True
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

        # Character creation sets the FKs and auto-applies starting equipment
        character.refresh_from_db()
        assert character.class_option is not None
        assert character.background_option is not None
        assert character.starting_equipment_claimed is True

        # Verify ledger entry created
        entries = LedgerEntry.objects.filter(character=character)
        assert entries.count() == 1
        entry = entries.first()
        assert entry.kind == LedgerEntry.Kind.AWARD
        assert entry.note == "Starting equipment"


class TestClaimNoMatch:
    """Tests edge case: claim when template has no matching class/background."""

    def test_claim_with_no_matching_entries_returns_error_and_stays_unclaimed(
        self, club, login, player
    ):
        """
        Claim with template that has no matching class/background
        -> should return an error and NOT mark claimed (so the player can retry
        once a matching entry exists).
        """
        # Create template with NO matching entries for our character
        template = StartingEquipmentTemplate.objects.create(
            club=club, name="Mismatched Template", is_active=True
        )
        # Add entry for Wizard (not Fighter)
        wizard_class = CharacterClass.objects.get(club=club, name="Wizard")
        StartingEquipmentClassEntry.objects.create(
            template=template,
            class_option=wizard_class,
            min_level=1,
            max_level=20,
            coins_cp=1000,
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

        # Set FKs (seeded by the club fixture)
        fighter_class = CharacterClass.objects.get(club=club, name="Fighter")
        acolyte_bg = Background.objects.get(club=club, name="Acolyte")
        character.class_option = fighter_class
        character.background_option = acolyte_bg
        character.save(update_fields=["class_option", "background_option"])

        # POST claim -> error, nothing granted, not marked claimed
        response = client.post(claim_url(club, character), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"

        character.refresh_from_db()
        assert character.starting_equipment_claimed is False

        # No ledger entry should be created (nothing to grant)
        assert LedgerEntry.objects.filter(character=character).count() == 0


class TestNoDoubleGrant:
    """Tests that approved magic requests are not double-granted on claim."""

    def test_approve_then_claim_grants_item_once(
        self,
        club,
        login,
        player,
        game_master,
        character_with_class_bg,
        template,
        class_entry,
        magic_option,
    ):
        """
        Approve a magic request (grants item via ledger), then claim.
        The item must appear exactly once in the ledger (no double grant).

        The fixtures already provide a Fighter class entry (1000cp) and an
        Acolyte background entry (500cp) on the template. We add a Longsword
        line to the class entry so the claim grants an item plus coins.
        """
        from items.models import Item
        from starting_equipment.models import StartingEquipmentClassLine

        # Add a Longsword line to the existing fixture class entry
        longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        StartingEquipmentClassLine.objects.create(
            class_entry=class_entry, item=longsword, quantity=1, is_choice=False
        )
        magic_item = magic_option.item

        # 1. Create a PENDING magic request
        req = StartingEquipmentRequest.objects.create(
            club=club,
            character=character_with_class_bg,
            item=magic_item,
            quantity=1,
            status=StartingEquipmentRequest.Status.PENDING,
        )

        # 2. GM approves it -> request_decide grants the item via ledger
        decide_url = reverse(
            "starting_equipment:request_decide",
            kwargs={"club_slug": club.slug, "pk": req.pk, "decision": "approve"},
        )
        client = login(game_master)
        response = client.post(decide_url, HTTP_HX_REQUEST="true")
        assert response.status_code == 204

        # Verify item was granted once by the approval
        potion_count = 0
        for e in LedgerEntry.objects.filter(character=character_with_class_bg):
            for line in e.lines.select_related("item"):
                if line.item == magic_item:
                    potion_count += 1
        assert potion_count == 1  # granted once by approval

        # 3. Player claims starting equipment -> grants class item + coins, not the potion again
        client = login(player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"

        # 4. Verify potion still appears exactly once (no double grant)
        potion_count = 0
        longsword_count = 0
        for e in LedgerEntry.objects.filter(character=character_with_class_bg):
            for line in e.lines.select_related("item"):
                if line.item == magic_item:
                    potion_count += 1
                if line.item == longsword:
                    longsword_count += 1
        assert potion_count == 1  # still exactly once (no double grant)
        assert longsword_count == 1  # class item granted by the claim
