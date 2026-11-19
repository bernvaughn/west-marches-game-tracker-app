"""Tests for the claim_starting_equipment view."""

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from ledger.models import LedgerEntry
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentClassEntry,
    StartingEquipmentTemplate,
)

pytestmark = [pytest.mark.django_db]


def claim_url(club, character):
    return reverse(
        "starting_equipment:claim",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


def create_url(club):
    return reverse("characters:create", kwargs={"club_slug": club.slug})


def flash_messages(response):
    """Return the list of flash message strings queued on the response's request."""
    return [str(m) for m in get_messages(response.wsgi_request)]


class TestClaimPermissions:
    """Tests for claim view permissions."""

    def test_owner_can_claim(self, club, login, player, character_with_class_bg, template):
        """Character owner can claim starting equipment."""
        client = login(player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"
        assert "Starting equipment claimed." in flash_messages(response)

    def test_club_admin_can_claim(self, club, login, club_admin, character_with_class_bg, template):
        """Club admin can claim starting equipment for any character."""
        client = login(club_admin)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"

    def test_game_master_can_claim(
        self, club, login, game_master, character_with_class_bg, template
    ):
        """Game master can claim starting equipment for any character."""
        client = login(game_master)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"

    def test_other_member_cannot_claim(
        self, club, login, other_player, character_with_class_bg, template
    ):
        """Non-owner/non-admin/non-GM gets 404."""
        client = login(other_player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 404


class TestClaimPostOnly:
    """Tests that the view is POST-only."""

    def test_get_returns_405(self, club, login, player, character_with_class_bg, template):
        """GET request returns 405 Method Not Allowed."""
        client = login(player)
        response = client.get(claim_url(club, character_with_class_bg))
        assert response.status_code == 405


class TestClaimAlreadyClaimed:
    """Tests idempotency - second claim is rejected."""

    def test_second_claim_rejected(self, club, login, player, character_with_class_bg, template):
        """Claiming twice returns error on second attempt."""
        client = login(player)

        # First claim succeeds
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        character_with_class_bg.refresh_from_db()
        assert character_with_class_bg.starting_equipment_claimed is True

        # Second claim returns error + refresh
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"
        assert "already been claimed" in " ".join(flash_messages(response))

    def test_claim_flag_set_even_if_no_equipment_granted(
        self, club, login, player, character_with_class_bg, empty_template
    ):
        """Character is NOT marked claimed when template grants nothing; error shown."""
        # Deactivate the main template and activate the empty one
        template = StartingEquipmentTemplate.objects.get(club=club, name="Test Template")
        template.is_active = False
        template.save()
        empty_template.is_active = True
        empty_template.save()

        client = login(player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"
        assert "No starting equipment matches" in " ".join(flash_messages(response))

        character_with_class_bg.refresh_from_db()
        assert character_with_class_bg.starting_equipment_claimed is False


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

        # POST claim -> error, nothing granted, not marked claimed
        response = client.post(claim_url(club, character), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"
        assert "No starting equipment matches" in " ".join(flash_messages(response))

        character.refresh_from_db()
        assert character.starting_equipment_claimed is False

        # No ledger entry should be created (nothing to grant)
        assert LedgerEntry.objects.filter(character=character).count() == 0


class TestClaimSuccess:
    """Tests successful claim flow."""

    def test_success_sets_claimed_flag(
        self, club, login, player, character_with_class_bg, template
    ):
        """Successful claim sets starting_equipment_claimed=True."""
        client = login(player)
        client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")

        character_with_class_bg.refresh_from_db()
        assert character_with_class_bg.starting_equipment_claimed is True

    def test_success_grants_equipment_via_ledger(
        self, club, login, player, character_with_class_bg, template, class_entry, bg_entry
    ):
        """Successful claim grants equipment via ledger."""
        client = login(player)
        client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")

        # Check ledger entry created
        assert LedgerEntry.objects.filter(
            character=character_with_class_bg,
            kind=LedgerEntry.Kind.AWARD,
            note="Starting equipment",
        ).exists()


class TestClaimNoTemplate:
    """Tests error when no active template exists."""

    def test_no_active_template_returns_error(
        self, club, login, player, character_with_class_bg, template
    ):
        """No active template returns error + refresh."""
        # Deactivate the template
        template.is_active = False
        template.save()

        client = login(player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"
        assert "No active starting equipment template" in " ".join(flash_messages(response))

    def test_no_active_template_flag_not_set(
        self, club, login, player, character_with_class_bg, template
    ):
        """When no template, claimed flag is not set."""
        template.is_active = False
        template.save()

        client = login(player)
        client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")

        character_with_class_bg.refresh_from_db()
        assert character_with_class_bg.starting_equipment_claimed is False


class TestClaimUrlResolve:
    """Tests for URL resolution."""

    def test_claim_url(self, club, character_with_class_bg):
        url = reverse(
            "starting_equipment:claim",
            kwargs={"club_slug": club.slug, "character_pk": character_with_class_bg.pk},
        )
        assert (
            url
            == f"/c/{club.slug}/starting-equipment/characters/{character_with_class_bg.pk}/claim/"
        )
