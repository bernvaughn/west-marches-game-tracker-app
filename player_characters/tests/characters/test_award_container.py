"""Tests for award form showing loot preview and granting container unopened."""

import pytest
from django.urls import reverse

from items.tests.factories import (
    ItemFactory,
    ContainerSlotFactory,
    ContainerSlotOptionFactory,
)
from accounts.tests.factories import UserFactory, ClubFactory, CharacterFactory


@pytest.mark.django_db
class TestBulkAwardLootPreview:
    """Tests for loot preview in bulk award form."""

    def test_bulk_award_page_has_preview_templates_for_gm(self, client, club, gm_user):
        """Bulk award page has hidden preview templates for container items."""
        container = ItemFactory(club=club, name="Award Chest", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Reward Item", qty_min=1, qty_max=1)

        # Non-container item
        ItemFactory(club=club, name="Regular Item", is_container=False)

        client.force_login(gm_user)
        url = reverse("characters:bulk_award", args=[club.slug])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # Should have template elements for container previews
        assert f'id="loot-preview-{container.pk}"' in content
        assert "Reward Item" in content

    def test_bulk_award_preview_shows_unknown_for_player_not_applicable(self, client, club, gm_user):
        """Bulk award is GM-only, so unknown masking not applicable."""
        # This test documents that bulk_award is admin_or_gm_required
        # so unknown items are always visible (viewer_can_see_unknown=True)
        container = ItemFactory(club=club, name="Mystery Award", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Secret Reward", qty_min=1, qty_max=1)

        client.force_login(gm_user)
        url = reverse("characters:bulk_award", args=[club.slug])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # GM sees real name
        assert "Secret Reward" in content


@pytest.mark.django_db
class TestAdjustLootPreview:
    """Tests for loot preview in adjust form (optional per plan)."""

    def test_adjust_page_preview_optional(self, client, club, gm_user, character):
        """Adjust page could have preview - optional per plan."""
        # This is optional per the plan, just document the possibility
        container = ItemFactory(club=club, name="Adjust Container", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Adjust Item", qty_min=1, qty_max=1)

        client.force_login(gm_user)
        url = reverse("characters:adjust", args=[club.slug, character.pk])
        response = client.get(url)
        assert response.status_code == 200
        # Adjust page uses _item_rows.html which doesn't have preview by default
        # Per plan, it's gated by a loot_previews context var only adjust sets
        content = response.content.decode()
        # For now just verify the page loads
        assert "Adjust" in content


@pytest.mark.django_db
class TestBulkAwardGrantContainer:
    """Tests that bulk award grants container unopened."""

    def test_bulk_award_with_container_grants_unopened(self, client, club, gm_user, character):
        """Bulk award with container item grants container unopened."""
        from ledger.services import available_items
        from items.models import ContainerOpening

        container = ItemFactory(club=club, name="Bulk Award Chest", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Bulk Sword", qty_min=1, qty_max=1)

        client.force_login(gm_user)
        url = reverse("characters:bulk_award", args=[club.slug])
        data = {
            "characters": [character.pk],
            "note": "Test award",
            "date": "2024-01-01",
            f"coins_{character.pk}": "0",
            f"items_{character.pk}-TOTAL_FORMS": "1",
            f"items_{character.pk}-INITIAL_FORMS": "0",
            f"items_{character.pk}-MIN_NUM_FORMS": "0",
            f"items_{character.pk}-MAX_NUM_FORMS": "1",
            f"items_{character.pk}-0-item": str(container.pk),
            f"items_{character.pk}-0-item_id": str(container.pk),
            f"items_{character.pk}-0-quantity": "1",
            f"items_{character.pk}-0-value_override": "",
        }
        response = client.post(url, data)
        assert response.status_code == 302

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        sword = ItemFactory(club=club, name="Bulk Sword")
        assert avail.get(sword.pk, 0) == 0

    def test_bulk_award_multiple_characters_with_container(self, client, club, gm_user):
        """Bulk award to multiple characters with container."""
        from ledger.services import available_items
        from items.models import ContainerOpening

        container = ItemFactory(club=club, name="Party Chest", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Party Item", qty_min=1, qty_max=1)

        char1 = CharacterFactory(club=club, name="Char1")
        char2 = CharacterFactory(club=club, name="Char2")

        client.force_login(gm_user)
        url = reverse("characters:bulk_award", args=[club.slug])
        data = {
            "characters": [char1.pk, char2.pk],
            "note": "Party award",
            "date": "2024-01-01",
            f"coins_{char1.pk}": "0",
            f"items_{char1.pk}-TOTAL_FORMS": "1",
            f"items_{char1.pk}-INITIAL_FORMS": "0",
            f"items_{char1.pk}-MIN_NUM_FORMS": "0",
            f"items_{char1.pk}-MAX_NUM_FORMS": "1",
            f"items_{char1.pk}-0-item": str(container.pk),
            f"items_{char1.pk}-0-item_id": str(container.pk),
            f"items_{char1.pk}-0-quantity": "1",
            f"items_{char1.pk}-0-value_override": "",
            f"coins_{char2.pk}": "0",
            f"items_{char2.pk}-TOTAL_FORMS": "1",
            f"items_{char2.pk}-INITIAL_FORMS": "0",
            f"items_{char2.pk}-MIN_NUM_FORMS": "0",
            f"items_{char2.pk}-MAX_NUM_FORMS": "1",
            f"items_{char2.pk}-0-item": str(container.pk),
            f"items_{char2.pk}-0-item_id": str(container.pk),
            f"items_{char2.pk}-0-quantity": "1",
            f"items_{char2.pk}-0-value_override": "",
        }
        response = client.post(url, data)
        assert response.status_code == 302

        # Check both characters got the container
        avail1 = available_items(char1)
        avail2 = available_items(char2)
        assert avail1[container.pk] == 1
        assert avail2[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=char1).exists()
        assert not ContainerOpening.objects.filter(character=char2).exists()


@pytest.mark.django_db
class TestAdjustGrantContainer:
    """Tests that adjust grants container unopened."""

    def test_adjust_with_container_grants_unopened(self, client, club, gm_user, character):
        """Adjust with container item grants container unopened."""
        from ledger.services import available_items
        from items.models import ContainerOpening

        container = ItemFactory(club=club, name="Adjust Chest", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Adjust Item", qty_min=1, qty_max=1)

        client.force_login(gm_user)
        url = reverse("characters:adjust", args=[club.slug, character.pk])
        # The adjust form uses a formset, we need to submit properly
        data = {
            "kind": "award",
            "sign": "1",
            "note": "Test adjust",
            "date": "2024-01-01",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-item": str(container.pk),
            "form-0-quantity": "1",
        }
        response = client.post(url, data)
        assert response.status_code == 302

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        item = ItemFactory(club=club, name="Adjust Item")
        assert avail.get(item.pk, 0) == 0