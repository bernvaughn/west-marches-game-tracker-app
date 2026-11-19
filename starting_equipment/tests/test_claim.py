"""Tests for the claim_starting_equipment view."""

import json

import pytest
from django.urls import reverse

from starting_equipment.models import StartingEquipmentTemplate

pytestmark = [pytest.mark.django_db]


def claim_url(club, character):
    return reverse(
        "starting_equipment:claim",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


class TestClaimPermissions:
    """Tests for claim view permissions."""

    def test_owner_can_claim(self, club, login, player, character_with_class_bg, template):
        """Character owner can claim starting equipment."""
        client = login(player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204

    def test_club_admin_can_claim(self, club, login, club_admin, character_with_class_bg, template):
        """Club admin can claim starting equipment for any character."""
        client = login(club_admin)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204

    def test_game_master_can_claim(
        self, club, login, game_master, character_with_class_bg, template
    ):
        """Game master can claim starting equipment for any character."""
        client = login(game_master)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204

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

        # Second claim returns error
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 400
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["claimError"] == "Already claimed"

    def test_claim_flag_set_even_if_no_equipment_granted(
        self, club, login, player, character_with_class_bg, empty_template
    ):
        """Character is marked claimed even when template grants nothing."""
        # Deactivate the main template and activate the empty one
        template = StartingEquipmentTemplate.objects.get(club=club, name="Test Template")
        template.is_active = False
        template.save()
        empty_template.is_active = True
        empty_template.save()

        client = login(player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
        assert response.status_code == 204

        character_with_class_bg.refresh_from_db()
        assert character_with_class_bg.starting_equipment_claimed is True


class TestClaimSuccess:
    """Tests successful claim flow."""

    def test_success_sets_htmx_triggers(
        self, club, login, player, character_with_class_bg, template
    ):
        """Successful claim returns 204 with HTMX triggers."""
        client = login(player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["appModalClose"] is True
        assert trigger["characterSheetRefresh"] is True

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
        from ledger.models import LedgerEntry

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
        """No active template returns error response."""
        # Deactivate the template
        template.is_active = False
        template.save()

        client = login(player)
        response = client.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")

        assert response.status_code == 400
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["claimError"] == "No active starting equipment template"

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
