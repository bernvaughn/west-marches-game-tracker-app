"""Tests for stacked items in agent item search."""

import pytest

from items.models import Item
from items.tests.factories import make_container, make_stacked


def sc(mcp, secret, tool, **args):
    """Helper to call a tool and assert success."""
    status, result = mcp(secret, tool, **args)
    assert status == 200 and not result.get("isError")
    return result["structuredContent"]


@pytest.fixture
def parchment(club):
    """Stacked item: 100 cp per 10 sheets."""
    return make_stacked(club, "Parchment", "sheet", 100, 10)


@pytest.fixture
def rope(club):
    """Stacked item: 100 cp per 50 ft."""
    return make_stacked(club, "Rope", "ft", 100, 50)


@pytest.fixture
def sword(club):
    """Normal item."""
    return Item.objects.create(club=club, name="Longsword", value_cp=1500)


@pytest.fixture
def container_with_stacked(club, parchment):
    """Container with stacked item in loot."""
    container = make_container(club, "Parchment Box")
    from items.models import ContainerSlot, ContainerSlotOption

    slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0)
    ContainerSlotOption.objects.create(slot=slot, item=parchment, qty_min=1, qty_max=3, weight=1)
    return container


@pytest.mark.django_db
class TestAgentSearchItemsStacked:
    """Tests for search_items with stacked items."""

    def test_search_items_shows_stacked_fields(
        self, mcp, gm_connection, club, parchment, rope, sword
    ):
        """search_items shows is_stacked, unit_name, value_units for stacked and normal items."""
        result = sc(mcp, gm_connection[1], "search_items", query="", limit=10)

        items = result["items"]
        # Find our test items
        parchment_data = next(i for i in items if i["id"] == parchment.pk)
        rope_data = next(i for i in items if i["id"] == rope.pk)
        sword_data = next(i for i in items if i["id"] == sword.pk)

        # Stacked item fields
        assert parchment_data["is_stacked"] is True
        assert parchment_data["unit_name"] == "sheet"
        assert parchment_data["value_units"] == 10

        assert rope_data["is_stacked"] is True
        assert rope_data["unit_name"] == "ft"
        assert rope_data["value_units"] == 50

        # Normal item fields
        assert sword_data["is_stacked"] is False
        assert sword_data["unit_name"] == ""
        assert sword_data["value_units"] == 1

        # All previous keys still present
        expected_keys = {
            "id",
            "name",
            "description",
            "traits",
            "gm_details",
            "value_cp",
            "value",
            "is_container",
            "is_stacked",
            "unit_name",
            "value_units",
        }
        for item_data in [parchment_data, rope_data, sword_data]:
            assert set(item_data.keys()) == expected_keys

    def test_other_club_items_never_returned(self, mcp, gm_connection, club, other_club, parchment):
        """Other club's items never returned."""
        other_item = Item.objects.create(club=other_club, name="Other Rope", value_cp=100)

        result = sc(mcp, gm_connection[1], "search_items", query="", limit=10)

        item_ids = [i["id"] for i in result["items"]]
        assert other_item.pk not in item_ids

    def test_masked_loot_rows_never_leak(
        self, mcp, gm_connection, club, container_with_stacked, parchment
    ):
        """Masked loot rows never leak item info."""
        # Make the slot unknown
        from items.models import ContainerSlot

        slot = ContainerSlot.objects.get(container=container_with_stacked)
        slot.unknown = True
        slot.save()

        result = sc(mcp, gm_connection[1], "search_items", query="Parchment Box", limit=10)

        container_data = next(i for i in result["items"] if i["id"] == container_with_stacked.pk)
        assert "loot" in container_data

        loot_rows = container_data["loot"]
        assert len(loot_rows) == 1
        row = loot_rows[0]
        # Masked row should not have item name or id
        assert row["label"] == "???"
        assert "item_id" not in row or row.get("item_id") is None
        assert "item_name" not in row or row.get("item_name") is None
        assert row["unit_name"] == ""

    def test_container_loot_rows_have_unit_name(
        self, mcp, gm_connection, club, container_with_stacked, parchment
    ):
        """Container loot rows have unit_name for stacked items."""
        result = sc(mcp, gm_connection[1], "search_items", query="Parchment Box", limit=10)

        container_data = next(i for i in result["items"] if i["id"] == container_with_stacked.pk)
        loot_rows = container_data["loot"]

        assert len(loot_rows) == 1
        row = loot_rows[0]
        assert row["unit_name"] == "sheet"
        assert row["qty_min"] == 1
        assert row["qty_max"] == 3

    def test_one_of_container_loot_rows_have_unit_name(
        self, mcp, gm_connection, club, parchment, rope
    ):
        """Container with multiple options shows unit_name for each."""
        container = make_container(club, "Multi Box")
        from items.models import ContainerSlot, ContainerSlotOption

        slot = ContainerSlot.objects.create(container=container, chance_pct=100, position=0)
        ContainerSlotOption.objects.create(
            slot=slot, item=parchment, qty_min=1, qty_max=1, weight=3
        )
        ContainerSlotOption.objects.create(slot=slot, item=rope, qty_min=10, qty_max=20, weight=1)

        result = sc(mcp, gm_connection[1], "search_items", query="Multi Box", limit=10)

        container_data = next(i for i in result["items"] if i["id"] == container.pk)
        loot_rows = container_data["loot"]

        assert len(loot_rows) == 1
        row = loot_rows[0]
        assert row["label"] == "One of"
        assert len(row["options"]) == 2
        # Check unit_name in options
        opt1 = row["options"][0]
        assert opt1["unit_name"] == "sheet"
        opt2 = row["options"][1]
        assert opt2["unit_name"] == "ft"

    def test_previous_keys_unchanged(self, mcp, gm_connection, club, sword):
        """Every previous key still present in search_items response."""
        result = sc(mcp, gm_connection[1], "search_items", query="Longsword", limit=10)

        item_data = result["items"][0]
        # Old keys that must still exist
        old_keys = {
            "id",
            "name",
            "description",
            "traits",
            "gm_details",
            "value_cp",
            "value",
            "is_container",
        }
        for key in old_keys:
            assert key in item_data, f"Missing key: {key}"

        # New keys added
        assert "is_stacked" in item_data
        assert "unit_name" in item_data
        assert "value_units" in item_data
