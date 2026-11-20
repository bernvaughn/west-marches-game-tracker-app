"""Tests for stacked items in containers."""

import pytest

from items.containers import loot_preview, roll_container
from items.models import ContainerSlot, ContainerSlotOption, Item
from items.tests.factories import make_container, make_stacked


@pytest.mark.django_db
class TestStackedContainers:
    """Tests for container slots with stacked items."""

    def test_opening_container_with_stacked_option_gives_units(self, club):
        """Opening a container with a stacked option gives units."""
        container = make_container(club, "Test Box")
        parchment = make_stacked(club, "Parchment", "sheet", 100, 10)
        
        slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0)
        ContainerSlotOption.objects.create(slot=slot, item=parchment, qty_min=1, qty_max=3, weight=1)
        
        # Roll the container
        roll = roll_container(container)
        
        assert len(roll.slots) == 1
        assert roll.slots[0].hit is True
        assert roll.slots[0].item_id == parchment.pk
        assert 1 <= roll.slots[0].qty <= 3
        # Ledger lines should have the rolled quantity
        assert roll.lines[parchment] == roll.slots[0].qty

    def test_preview_row_unit_name_set_and_rendered(self, club):
        """Preview row has unit_name set and renders correctly."""
        container = make_container(club, "Test Box")
        parchment = make_stacked(club, "Parchment", "sheet", 100, 10)
        
        slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0)
        ContainerSlotOption.objects.create(slot=slot, item=parchment, qty_min=2, qty_max=2, weight=1)
        
        preview = loot_preview(container, viewer_can_see_unknown=True)
        
        assert len(preview) == 1
        row = preview[0]
        assert row.item == parchment
        assert row.unit_name == "sheet"
        assert row.qty_min == 2
        assert row.qty_max == 2

    def test_preview_one_of_stacked_options(self, club):
        """Preview with multiple stacked options shows unit_name for each."""
        container = make_container(club, "Test Box")
        parchment = make_stacked(club, "Parchment", "sheet", 100, 10)
        rope = make_stacked(club, "Rope", "ft", 100, 50)
        
        slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0)
        ContainerSlotOption.objects.create(slot=slot, item=parchment, qty_min=1, qty_max=1, weight=3)
        ContainerSlotOption.objects.create(slot=slot, item=rope, qty_min=10, qty_max=20, weight=1)
        
        preview = loot_preview(container, viewer_can_see_unknown=True)
        
        assert len(preview) == 1
        row = preview[0]
        assert row.label == "One of"
        assert len(row.options) == 2
        # First option
        opt1 = row.options[0]
        assert opt1.item == parchment
        assert opt1.unit_name == "sheet"
        # Second option
        opt2 = row.options[1]
        assert opt2.item == rope
        assert opt2.unit_name == "ft"

    def test_unknown_slot_stays_masked_for_player(self, club):
        """Unknown slot stays masked for player."""
        container = make_container(club, "Test Box")
        parchment = make_stacked(club, "Parchment", "sheet", 100, 10)
        
        slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0, unknown=True)
        ContainerSlotOption.objects.create(slot=slot, item=parchment, qty_min=1, qty_max=1, weight=1)
        
        # Player view (viewer_can_see_unknown=False)
        preview = loot_preview(container, viewer_can_see_unknown=False)
        
        assert len(preview) == 1
        row = preview[0]
        assert row.masked is True
        assert row.item is None
        assert row.label == "???"
        assert row.unit_name == ""

    def test_unknown_slot_visible_to_gm(self, club):
        """Unknown slot is visible to GM."""
        container = make_container(club, "Test Box")
        parchment = make_stacked(club, "Parchment", "sheet", 100, 10)
        
        slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0, unknown=True)
        ContainerSlotOption.objects.create(slot=slot, item=parchment, qty_min=1, qty_max=1, weight=1)
        
        # GM view (viewer_can_see_unknown=True)
        preview = loot_preview(container, viewer_can_see_unknown=True)
        
        assert len(preview) == 1
        row = preview[0]
        assert row.masked is False
        assert row.item == parchment
        assert row.unit_name == "sheet"

    def test_retired_stacked_item_ok(self, club):
        """Retired stacked item works in container."""
        container = make_container(club, "Test Box")
        parchment = make_stacked(club, "Parchment", "sheet", 100, 10)
        parchment.retired = True
        parchment.save()
        
        slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0)
        ContainerSlotOption.objects.create(slot=slot, item=parchment, qty_min=1, qty_max=1, weight=1)
        
        preview = loot_preview(container, viewer_can_see_unknown=True)
        
        assert len(preview) == 1
        row = preview[0]
        assert row.item == parchment
        assert row.unit_name == "sheet"

    def test_normal_item_no_unit_name(self, club):
        """Normal item has empty unit_name."""
        container = make_container(club, "Test Box")
        sword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        
        slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0)
        ContainerSlotOption.objects.create(slot=slot, item=sword, qty_min=1, qty_max=1, weight=1)
        
        preview = loot_preview(container, viewer_can_see_unknown=True)
        
        assert len(preview) == 1
        row = preview[0]
        assert row.item == sword
        assert row.unit_name == ""