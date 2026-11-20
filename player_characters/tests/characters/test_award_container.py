"""Tests for award form showing loot preview and granting container unopened."""

import pytest
from django.urls import reverse

from items.models import ContainerOpening
from items.tests.factories import _get_or_create_item, add_slot, make_container
from ledger.services import available_items
from player_characters.models import Character
from accounts.models import Membership


@pytest.fixture
def container_award_chest(club):
    """Container for award chest."""
    container = make_container(club, name="Award Chest")
    reward = _get_or_create_item(club, "Reward Item")
    add_slot(container, [(reward, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_mystery_award(club):
    """Container with unknown award."""
    container = make_container(club, name="Mystery Award")
    secret = _get_or_create_item(club, "Secret Reward")
    add_slot(container, [(secret, 1, 1, 1)], chance_pct=100, unknown=True)
    return container


@pytest.fixture
def container_bulk_award_chest(club):
    """Container for bulk award."""
    container = make_container(club, name="Bulk Award Chest")
    sword = _get_or_create_item(club, "Bulk Sword")
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_party_chest(club):
    """Container for party chest."""
    container = make_container(club, name="Party Chest")
    item = _get_or_create_item(club, "Party Item")
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_adjust_chest(club):
    """Container for adjust."""
    container = make_container(club, name="Adjust Chest")
    item = _get_or_create_item(club, "Adjust Item")
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.mark.django_db
class TestBulkAwardLootPreview:
    """Tests for loot preview in bulk award form."""

    def test_bulk_award_page_has_preview_templates_for_gm(
        self, client, club, game_master, container_award_chest
    ):
        """Bulk award page has hidden preview templates for container items."""
        # Non-container item
        _get_or_create_item(club, name="Regular Item", is_container=False)

        client.force_login(game_master)
        url = reverse("characters:bulk_award", args=[club.slug])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # Should have template elements for container previews
        assert f'id="loot-preview-{container_award_chest.pk}"' in content
        assert "Reward Item" in content

    def test_bulk_award_preview_shows_unknown_for_player_not_applicable(
        self, client, club, game_master, container_mystery_award
    ):
        """Bulk award is GM-only, so unknown masking not applicable."""
        # This test documents that bulk_award is admin_or_gm_required
        # so unknown items are always visible (viewer_can_see_unknown=True)
        client.force_login(game_master)
        url = reverse("characters:bulk_award", args=[club.slug])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # GM sees real name
        assert "Secret Reward" in content


@pytest.mark.django_db
class TestAdjustLootPreview:
    """Tests for loot preview in adjust form (optional per plan)."""

    def test_adjust_page_preview_optional(self, client, club, game_master, character):
        """Adjust page could have preview - optional per plan."""
        # This is optional per the plan, just document the possibility
        container = make_container(club, name="Adjust Container")
        item = _get_or_create_item(club, "Adjust Item")
        add_slot(container, [(item, 1, 1, 1)], chance_pct=100, unknown=False)

        client.force_login(game_master)
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

    def test_bulk_award_with_container_grants_unopened(
        self, client, club, game_master, character, container_bulk_award_chest
    ):
        """Bulk award with container item grants container unopened."""
        client.force_login(game_master)
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
            f"items_{character.pk}-0-item": str(container_bulk_award_chest.pk),
            f"items_{character.pk}-0-item_id": str(container_bulk_award_chest.pk),
            f"items_{character.pk}-0-quantity": "1",
            f"items_{character.pk}-0-value_override": "",
        }
        response = client.post(url, data)
        assert response.status_code == 302

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container_bulk_award_chest.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        sword = _get_or_create_item(club, name="Bulk Sword")
        assert avail.get(sword.pk, 0) == 0

    def test_bulk_award_multiple_characters_with_container(
        self, client, club, game_master, container_party_chest
    ):
        """Bulk award to multiple characters with container."""
        from accounts.models import Membership

        owner = Membership.objects.get(user=game_master, club=club)
        char1 = Character.objects.create(club=club, owner=owner, name="Char1")
        char2 = Character.objects.create(club=club, owner=owner, name="Char2")

        client.force_login(game_master)
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
            f"items_{char1.pk}-0-item": str(container_party_chest.pk),
            f"items_{char1.pk}-0-item_id": str(container_party_chest.pk),
            f"items_{char1.pk}-0-quantity": "1",
            f"items_{char1.pk}-0-value_override": "",
            f"coins_{char2.pk}": "0",
            f"items_{char2.pk}-TOTAL_FORMS": "1",
            f"items_{char2.pk}-INITIAL_FORMS": "0",
            f"items_{char2.pk}-MIN_NUM_FORMS": "0",
            f"items_{char2.pk}-MAX_NUM_FORMS": "1",
            f"items_{char2.pk}-0-item": str(container_party_chest.pk),
            f"items_{char2.pk}-0-item_id": str(container_party_chest.pk),
            f"items_{char2.pk}-0-quantity": "1",
            f"items_{char2.pk}-0-value_override": "",
        }
        response = client.post(url, data)
        assert response.status_code == 302

        # Check both characters got the container
        avail1 = available_items(char1)
        avail2 = available_items(char2)
        assert avail1[container_party_chest.pk] == 1
        assert avail2[container_party_chest.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=char1).exists()
        assert not ContainerOpening.objects.filter(character=char2).exists()


@pytest.mark.django_db
class TestAdjustGrantContainer:
    """Tests that adjust grants container unopened."""

    def test_adjust_with_container_grants_unopened(
        self, client, club, game_master, character, container_adjust_chest
    ):
        """Adjust with container item grants container unopened."""
        client.force_login(game_master)
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
            "form-0-item": str(container_adjust_chest.pk),
            "form-0-quantity": "1",
        }
        response = client.post(url, data)
        assert response.status_code == 302

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container_adjust_chest.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        item = _get_or_create_item(club, name="Adjust Item")
        assert avail.get(item.pk, 0) == 0
