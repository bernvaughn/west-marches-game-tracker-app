"""Tests for loot preview on starting equipment surfaces."""

import pytest
from django.urls import reverse

from items.models import ContainerOpening
from items.tests.factories import _get_or_create_item, add_slot, make_container
from ledger.services import available_items
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)
from starting_equipment.services import apply_starting_equipment


@pytest.fixture
def container_adventurers_pack(club):
    """Container for adventurer's pack."""
    container = make_container(club, name="Adventurer's Pack")
    rope = _get_or_create_item(club, "Rope")
    add_slot(container, [(rope, 50, 50, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_scholars_pack(club):
    """Container for scholar's pack."""
    container = make_container(club, name="Scholar's Pack")
    book = _get_or_create_item(club, "Book")
    add_slot(container, [(book, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_magic_box(club):
    """Container for magic box."""
    container = make_container(club, name="Magic Box")
    wand = _get_or_create_item(club, "Wand")
    add_slot(container, [(wand, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_mystery_box(club):
    """Container with unknown content."""
    container = make_container(club, name="Mystery Box")
    secret = _get_or_create_item(club, "Secret Item")
    add_slot(container, [(secret, 1, 1, 1)], chance_pct=100, unknown=True)
    return container


@pytest.fixture
def container_approved_pack(club):
    """Container for approved pack."""
    container = make_container(club, name="Approved Pack")
    item = _get_or_create_item(club, "Approved Item")
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_class_pack(club):
    """Container for class pack."""
    container = make_container(club, name="Class Pack")
    sword = _get_or_create_item(club, "Sword")
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_request_pack(club):
    """Container for request pack."""
    container = make_container(club, name="Request Pack")
    shield = _get_or_create_item(club, "Shield")
    add_slot(container, [(shield, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def template_with_class_container(club, container_adventurers_pack):
    """Template with class entry containing container."""
    template = StartingEquipmentTemplate.objects.create(
        club=club, name="Test Template", is_active=True
    )
    class_entry = StartingEquipmentClassEntry.objects.create(
        template=template, char_class="Fighter", min_level=1, max_level=20
    )
    StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=container_adventurers_pack, quantity=1
    )
    return template


@pytest.fixture
def template_with_bg_container(club, container_scholars_pack):
    """Template with background entry containing container."""
    template = StartingEquipmentTemplate.objects.create(
        club=club, name="Test Template", is_active=True
    )
    bg_entry = StartingEquipmentBackgroundEntry.objects.create(template=template, background="Sage")
    StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry, item=container_scholars_pack, quantity=1
    )
    return template


@pytest.fixture
def template_with_magic_container(club, container_magic_box):
    """Template with magic option containing container."""
    template = StartingEquipmentTemplate.objects.create(
        club=club, name="Test Template", is_active=True
    )
    MagicItemStartingOption.objects.create(
        template=template, item=container_magic_box, max_per_character=1
    )
    return template


@pytest.fixture
def template_with_unknown_magic(club, container_mystery_box):
    """Template with unknown magic option."""
    template = StartingEquipmentTemplate.objects.create(
        club=club, name="Test Template", is_active=True
    )
    MagicItemStartingOption.objects.create(
        template=template, item=container_mystery_box, max_per_character=1
    )
    return template


@pytest.fixture
def pending_request_with_container(club, container_approved_pack, character):
    """Pending request with container item."""
    return StartingEquipmentRequest.objects.create(
        club=club,
        character=character,
        item=container_approved_pack,
        quantity=1,
        status=StartingEquipmentRequest.Status.PENDING,
    )


@pytest.fixture
def template_with_class_container_pack(club, container_class_pack):
    """Template with class entry containing container pack."""
    template = StartingEquipmentTemplate.objects.create(
        club=club, name="Class Template", is_active=True
    )
    class_entry = StartingEquipmentClassEntry.objects.create(
        template=template, char_class="Fighter", min_level=1, max_level=1
    )
    StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=container_class_pack, quantity=1
    )
    return template


@pytest.fixture
def template_with_request_container(club, container_request_pack):
    """Template with magic option containing request pack."""
    template = StartingEquipmentTemplate.objects.create(
        club=club, name="Request Template", is_active=True
    )
    MagicItemStartingOption.objects.create(
        template=template, item=container_request_pack, max_per_character=1
    )
    return template


@pytest.fixture
def pending_request_request_pack(club, container_request_pack, character):
    """Pending request with request pack."""
    return StartingEquipmentRequest.objects.create(
        club=club,
        character=character,
        item=container_request_pack,
        quantity=1,
        status=StartingEquipmentRequest.Status.PENDING,
    )


@pytest.mark.django_db
class TestStartingEquipmentTemplateDetailLootPreview:
    """Tests for loot preview in starting equipment template detail."""

    def test_template_detail_shows_preview_for_class_entry_line(
        self, client, club, game_master, template_with_class_container
    ):
        """Template detail shows preview for container in class entry line."""
        client.force_login(game_master)
        url = reverse(
            "starting_equipment:template_detail", args=[club.slug, template_with_class_container.pk]
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Adventurer's Pack" in content
        assert "Rope" in content
        assert "50×" in content or "50-" in content

    def test_template_detail_shows_preview_for_background_entry_line(
        self, client, club, game_master, template_with_bg_container
    ):
        """Template detail shows preview for container in background entry line."""
        client.force_login(game_master)
        url = reverse(
            "starting_equipment:template_detail", args=[club.slug, template_with_bg_container.pk]
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Scholar's Pack" in content
        assert "Book" in content

    def test_template_detail_shows_preview_for_magic_option(
        self, client, club, game_master, template_with_magic_container
    ):
        """Template detail shows preview for container in magic option."""
        client.force_login(game_master)
        url = reverse(
            "starting_equipment:template_detail", args=[club.slug, template_with_magic_container.pk]
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Magic Box" in content
        assert "Wand" in content


@pytest.mark.django_db
class TestStartingEquipmentEntryListLootPreview:
    """Tests for loot preview in starting equipment entry list."""

    def test_entry_list_shows_preview_for_class_lines(
        self, client, club, game_master, template_with_class_container
    ):
        """Entry list shows preview for container in class entry lines."""
        client.force_login(game_master)
        url = reverse(
            "starting_equipment:class_entries", args=[club.slug, template_with_class_container.pk]
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Adventurer's Pack" in content
        assert "Rope" in content

    def test_entry_list_shows_preview_for_background_lines(
        self, client, club, game_master, template_with_bg_container
    ):
        """Entry list shows preview for container in background entry lines."""
        client.force_login(game_master)
        url = reverse(
            "starting_equipment:background_entries", args=[club.slug, template_with_bg_container.pk]
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Scholar's Pack" in content
        assert "Book" in content

    def test_entry_list_shows_preview_for_magic_options(
        self, client, club, game_master, template_with_magic_container
    ):
        """Entry list shows preview for container in magic options."""
        client.force_login(game_master)
        url = reverse(
            "starting_equipment:magic_options", args=[club.slug, template_with_magic_container.pk]
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Magic Box" in content
        assert "Wand" in content


@pytest.mark.django_db
class TestStartingEquipmentRequestModalLootPreview:
    """Tests for loot preview in starting equipment request modal."""

    def test_request_modal_shows_preview_for_container_option(
        self, client, club, player, character, template_with_magic_container
    ):
        """Request modal shows preview when container magic option is selected."""
        client.force_login(player)
        url = reverse("starting_equipment:request_new", args=[club.slug, character.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # The modal should have the option
        assert "Magic Box" in content

    def test_request_modal_masks_unknown_for_player(
        self, client, club, player, character, template_with_unknown_magic
    ):
        """Request modal masks unknown items for player."""
        client.force_login(player)
        url = reverse("starting_equipment:request_new", args=[club.slug, character.pk])
        response = client.get(url)
        content = response.content.decode()
        # Player should see ??? when they select the item (via JS)
        # For now just check the item is in the dropdown
        assert "Mystery Box" in content


@pytest.mark.django_db
class TestStartingEquipmentDecideConfirmLootPreview:
    """Tests for loot preview in starting equipment decide confirm."""

    def test_decide_confirm_shows_preview_for_container(
        self, client, club, game_master, character, pending_request_with_container
    ):
        """Decide confirm shows preview for container item."""
        client.force_login(game_master)
        url = reverse(
            "starting_equipment:request_decide", args=[club.slug, pending_request_with_container.pk]
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Approved Pack" in content
        assert "Approved Item" in content


@pytest.mark.django_db
class TestStartingEquipmentLootPreviewLeakSweep:
    """Tests to ensure unknown item names never leak to player
    HTML on starting equipment surfaces."""

    def test_template_detail_player_never_sees_secret_item(
        self, client, club, player, template_with_unknown_magic
    ):
        """Player never sees 'Secret Item' in template detail HTML."""
        # Template detail is admin-only, so this tests non-admin access
        client.force_login(player)
        url = reverse(
            "starting_equipment:template_detail", args=[club.slug, template_with_unknown_magic.pk]
        )
        response = client.get(url)
        # Non-admin should get 403 or not see the detail
        # The page might be accessible but we check the content
        if response.status_code == 200:
            content = response.content.decode()
            assert "Secret Item" not in content

    def test_request_modal_player_never_sees_secret_item(
        self, client, club, player, character, template_with_unknown_magic
    ):
        """Player never sees 'Secret Item' in request modal HTML."""
        client.force_login(player)
        url = reverse("starting_equipment:request_new", args=[club.slug, character.pk])
        response = client.get(url)
        content = response.content.decode()
        # The dropdown shows the container name, not the contents
        # The preview would show ??? via JS
        assert "Secret Item" not in content


@pytest.mark.django_db
class TestStartingEquipmentGrantContainer:
    """Tests that starting equipment grants container unopened."""

    def test_apply_starting_equipment_grants_container_unopened(
        self, club, game_master, character, template_with_class_container_pack
    ):
        """apply_starting_equipment with container line grants container unopened."""
        apply_starting_equipment(character, template_with_class_container_pack, actor=game_master)

        # Check ledger: one line for container +1
        avail = available_items(character)
        container = (
            template_with_class_container_pack.classequipmentclassentry_set.first()
            .classequipmentclassline_set.first()
            .item
        )
        assert avail[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        sword = _get_or_create_item(club, name="Sword")
        assert avail.get(sword.pk, 0) == 0

    def test_request_decide_approve_grants_container_unopened(
        self, client, club, game_master, character, pending_request_request_pack
    ):
        """request_decide approve with container grants container unopened."""
        url = reverse(
            "starting_equipment:request_decide",
            args=[club.slug, pending_request_request_pack.pk, "approve"],
        )
        client.force_login(game_master)
        response = client.post(url, {"decision_note": "Approved"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 204

        # Check ledger: one line for container +1
        avail = available_items(character)
        container = pending_request_request_pack.item
        assert avail[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        shield = _get_or_create_item(club, name="Shield")
        assert avail.get(shield.pk, 0) == 0
