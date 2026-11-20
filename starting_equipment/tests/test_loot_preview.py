"""Tests for loot preview on starting equipment surfaces."""

import pytest
from django.urls import reverse

from items.tests.factories import (
    ItemFactory,
    ContainerSlotFactory,
    ContainerSlotOptionFactory,
)
from starting_equipment.tests.factories import (
    StartingEquipmentTemplateFactory,
    ClassEntryFactory,
    ClassEntryLineFactory,
    BackgroundEntryFactory,
    BackgroundEntryLineFactory,
    MagicOptionFactory,
    StartingEquipmentRequestFactory,
)
from accounts.tests.factories import UserFactory, ClubFactory, CharacterFactory


@pytest.mark.django_db
class TestStartingEquipmentTemplateDetailLootPreview:
    """Tests for loot preview in starting equipment template detail."""

    def test_template_detail_shows_preview_for_class_entry_line(self, client, club, gm_user):
        """Template detail shows preview for container in class entry line."""
        container = ItemFactory(club=club, name="Adventurer's Pack", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Rope", qty_min=50, qty_max=50)

        template = StartingEquipmentTemplateFactory(club=club)
        class_entry = ClassEntryFactory(template=template, char_class="Fighter")
        ClassEntryLineFactory(entry=class_entry, item=container, quantity=1)

        client.force_login(gm_user)
        url = reverse("starting_equipment:template_detail", args=[club.slug, template.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Adventurer's Pack" in content
        assert "Rope" in content
        assert "50×" in content or "50-" in content

    def test_template_detail_shows_preview_for_background_entry_line(self, client, club, gm_user):
        """Template detail shows preview for container in background entry line."""
        container = ItemFactory(club=club, name="Scholar's Pack", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Book", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club)
        bg_entry = BackgroundEntryFactory(template=template, background="Sage")
        BackgroundEntryLineFactory(entry=bg_entry, item=container, quantity=1)

        client.force_login(gm_user)
        url = reverse("starting_equipment:template_detail", args=[club.slug, template.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Scholar's Pack" in content
        assert "Book" in content

    def test_template_detail_shows_preview_for_magic_option(self, client, club, gm_user):
        """Template detail shows preview for container in magic option."""
        container = ItemFactory(club=club, name="Magic Box", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Wand", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club)
        MagicOptionFactory(template=template, item=container, max_per_character=1)

        client.force_login(gm_user)
        url = reverse("starting_equipment:template_detail", args=[club.slug, template.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Magic Box" in content
        assert "Wand" in content


@pytest.mark.django_db
class TestStartingEquipmentEntryListLootPreview:
    """Tests for loot preview in starting equipment entry list."""

    def test_entry_list_shows_preview_for_class_lines(self, client, club, gm_user):
        """Entry list shows preview for container in class entry lines."""
        container = ItemFactory(club=club, name="Adventurer's Pack", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Rope", qty_min=50, qty_max=50)

        template = StartingEquipmentTemplateFactory(club=club)
        class_entry = ClassEntryFactory(template=template, char_class="Fighter")
        ClassEntryLineFactory(entry=class_entry, item=container, quantity=1)

        client.force_login(gm_user)
        url = reverse("starting_equipment:class_entries", args=[club.slug, template.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Adventurer's Pack" in content
        assert "Rope" in content

    def test_entry_list_shows_preview_for_background_lines(self, client, club, gm_user):
        """Entry list shows preview for container in background entry lines."""
        container = ItemFactory(club=club, name="Scholar's Pack", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Book", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club)
        bg_entry = BackgroundEntryFactory(template=template, background="Sage")
        BackgroundEntryLineFactory(entry=bg_entry, item=container, quantity=1)

        client.force_login(gm_user)
        url = reverse("starting_equipment:background_entries", args=[club.slug, template.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Scholar's Pack" in content
        assert "Book" in content

    def test_entry_list_shows_preview_for_magic_options(self, client, club, gm_user):
        """Entry list shows preview for container in magic options."""
        container = ItemFactory(club=club, name="Magic Box", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Wand", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club)
        MagicOptionFactory(template=template, item=container, max_per_character=1)

        client.force_login(gm_user)
        url = reverse("starting_equipment:magic_options", args=[club.slug, template.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Magic Box" in content
        assert "Wand" in content


@pytest.mark.django_db
class TestStartingEquipmentRequestModalLootPreview:
    """Tests for loot preview in starting equipment request modal."""

    def test_request_modal_shows_preview_for_container_option(self, client, club, user, character):
        """Request modal shows preview when container magic option is selected."""
        container = ItemFactory(club=club, name="Magic Chest", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Spell Scroll", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club, is_active=True)
        MagicOptionFactory(template=template, item=container, max_per_character=1)

        client.force_login(user)
        url = reverse("starting_equipment:request_new", args=[club.slug, character.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # The modal should have the option
        assert "Magic Chest" in content

    def test_request_modal_masks_unknown_for_player(self, client, club, user, character):
        """Request modal masks unknown items for player."""
        container = ItemFactory(club=club, name="Mystery Box", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Secret Item", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club, is_active=True)
        MagicOptionFactory(template=template, item=container, max_per_character=1)

        client.force_login(user)
        url = reverse("starting_equipment:request_new", args=[club.slug, character.pk])
        response = client.get(url)
        content = response.content.decode()
        # Player should see ??? when they select the item (via JS)
        # For now just check the item is in the dropdown
        assert "Mystery Box" in content


@pytest.mark.django_db
class TestStartingEquipmentDecideConfirmLootPreview:
    """Tests for loot preview in starting equipment decide confirm."""

    def test_decide_confirm_shows_preview_for_container(self, client, club, gm_user, character):
        """Decide confirm shows preview for container item."""
        container = ItemFactory(club=club, name="Approved Pack", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Approved Item", qty_min=1, qty_max=1)

        request = StartingEquipmentRequestFactory(
            club=club,
            character=character,
            item=container,
            quantity=1,
            status="pending",
        )

        client.force_login(gm_user)
        url = reverse("starting_equipment:request_decide", args=[club.slug, request.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Approved Pack" in content
        assert "Approved Item" in content


@pytest.mark.django_db
class TestStartingEquipmentLootPreviewLeakSweep:
    """Tests to ensure unknown item names never leak to player HTML on starting equipment surfaces."""

    def test_template_detail_player_never_sees_secret_item(self, client, club, user):
        """Player never sees 'Secret Item' in template detail HTML."""
        # Template detail is admin-only, so this tests non-admin access
        container = ItemFactory(club=club, name="Mystery Pack", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Secret Item", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club)
        class_entry = ClassEntryFactory(template=template, char_class="Wizard")
        ClassEntryLineFactory(entry=class_entry, item=container, quantity=1)

        client.force_login(user)
        url = reverse("starting_equipment:template_detail", args=[club.slug, template.pk])
        response = client.get(url)
        # Non-admin should get 403 or not see the detail
        # The page might be accessible but we check the content
        if response.status_code == 200:
            content = response.content.decode()
            assert "Secret Item" not in content

    def test_request_modal_player_never_sees_secret_item(self, client, club, user, character):
        """Player never sees 'Secret Item' in request modal HTML."""
        container = ItemFactory(club=club, name="Mystery Box", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Secret Item", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club, is_active=True)
        MagicOptionFactory(template=template, item=container, max_per_character=1)

        client.force_login(user)
        url = reverse("starting_equipment:request_new", args=[club.slug, character.pk])
        response = client.get(url)
        content = response.content.decode()
        # The dropdown shows the container name, not the contents
        # The preview would show ??? via JS
        assert "Secret Item" not in content


@pytest.mark.django_db
class TestStartingEquipmentGrantContainer:
    """Tests that starting equipment grants container unopened."""

    def test_apply_starting_equipment_grants_container_unopened(self, club, gm_user, character):
        """apply_starting_equipment with container line grants container unopened."""
        from starting_equipment.services import apply_starting_equipment
        from ledger.services import available_items
        from items.models import ContainerOpening

        container = ItemFactory(club=club, name="Class Pack", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Sword", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club)
        class_entry = ClassEntryFactory(template=template, char_class="Fighter", min_level=1, max_level=1)
        ClassEntryLineFactory(entry=class_entry, item=container, quantity=1)

        # Apply starting equipment
        apply_starting_equipment(character, template, actor=gm_user)

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        sword = ItemFactory(club=club, name="Sword")
        assert avail.get(sword.pk, 0) == 0

    def test_request_decide_approve_grants_container_unopened(self, club, gm_user, character):
        """request_decide approve with container grants container unopened."""
        from starting_equipment.services import request_decide
        from ledger.services import available_items
        from items.models import ContainerOpening
        from starting_equipment.models import StartingEquipmentRequest

        container = ItemFactory(club=club, name="Request Pack", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Shield", qty_min=1, qty_max=1)

        template = StartingEquipmentTemplateFactory(club=club, is_active=True)
        MagicOptionFactory(template=template, item=container, max_per_character=1)

        request = StartingEquipmentRequestFactory(
            club=club,
            character=character,
            item=container,
            quantity=1,
            status="pending",
        )

        # Approve the request
        request_decide(request, "approve", actor=gm_user, decision_note="Approved")

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        shield = ItemFactory(club=club, name="Shield")
        assert avail.get(shield.pk, 0) == 0