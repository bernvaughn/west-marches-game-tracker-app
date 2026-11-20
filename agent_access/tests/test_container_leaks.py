"""Tests for container unknown-item leak audit in MCP/agent output."""

import json
import re
from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from items.containers import loot_preview
from items.models import Item
from items.tests.factories import add_slot, make_container

pytestmark = [pytest.mark.django_db]


def sc(mcp, secret, tool, **args):
    """Helper to call MCP tool and return structuredContent."""
    status, result = mcp(secret, tool, **args)
    assert status == 200 and not result.get("isError")
    return result["structuredContent"]


# ---------------------------------------------------------------------------
# MCP search_items leak tests
# ---------------------------------------------------------------------------


def test_search_items_container_returns_is_container_and_loot(mcp, gm_connection, club):
    """Container items include is_container and loot from loot_preview(False)."""
    secret = gm_connection[1]

    # Create a container with fixed, ranged, percent, one-of, and unknown slots
    container = make_container(club, "Test Chest")
    item1 = Item.objects.create(club=club, name="Gold Coin", value_cp=100)
    item2 = Item.objects.create(club=club, name="Silver Coin", value_cp=10)
    item3 = Item.objects.create(club=club, name="Gem", value_cp=5000)
    item4 = Item.objects.create(club=club, name="Sealed Scroll", value_cp=50)
    item5 = Item.objects.create(club=club, name="Mystery Item", value_cp=1000)

    add_slot(container, [(item1, 1, 1, 1)], chance_pct=100, position=0)  # fixed
    add_slot(container, [(item2, 1, 4, 1)], chance_pct=100, position=1)  # ranged
    add_slot(container, [(item3, 1, 1, 1)], chance_pct=30, position=2)  # percent
    add_slot(container, [(item4, 1, 1, 3), (item5, 1, 1, 1)], chance_pct=100, position=3)  # one of
    add_slot(container, [(item1, 1, 1, 1)], chance_pct=100, unknown=True, position=4)  # unknown

    item = sc(mcp, secret, "search_items", query="Test Chest")["items"][0]

    assert item["is_container"] is True
    assert "loot" in item
    loot = item["loot"]
    assert len(loot) == 5

    # Slot 0: fixed
    assert loot[0]["label"] == "Gold Coin"
    assert loot[0]["qty_min"] == 1
    assert loot[0]["qty_max"] == 1
    assert loot[0]["chance_pct"] == 100
    assert loot[0]["unknown"] is False
    assert loot[0]["options"] == []

    # Slot 1: ranged
    assert loot[1]["label"] == "Silver Coin"
    assert loot[1]["qty_min"] == 1
    assert loot[1]["qty_max"] == 4
    assert loot[1]["chance_pct"] == 100

    # Slot 2: percent chance
    assert loot[2]["label"] == "Gem"
    assert loot[2]["chance_pct"] == 30

    # Slot 3: one of
    assert loot[3]["label"] == "One of"
    assert loot[3]["qty_min"] is None
    assert loot[3]["qty_max"] is None
    assert len(loot[3]["options"]) == 2
    opt_labels = {o["label"] for o in loot[3]["options"]}
    assert opt_labels == {"Sealed Scroll", "Mystery Item"}
    for opt in loot[3]["options"]:
        assert "weight_pct" in opt
        assert opt["qty_min"] == 1
        assert opt["qty_max"] == 1

    # Slot 4: unknown -> masked
    assert loot[4]["label"] == "???"
    assert loot[4]["qty_min"] is None
    assert loot[4]["qty_max"] is None
    assert loot[4]["chance_pct"] == 100
    assert loot[4]["unknown"] is True
    assert loot[4]["options"] == []


def test_search_items_unknown_slot_never_leaks_real_name(mcp, gm_connection, club):
    """The real name of an unknown item never appears in the container's loot data."""
    secret = gm_connection[1]

    container = make_container(club, "Mystery Box")
    secret_item = Item.objects.create(club=club, name="SECRET DIARY", value_cp=1, symbol="📖")
    add_slot(container, [(secret_item, 1, 1, 1)], chance_pct=100, unknown=True, position=0)

    item = sc(mcp, secret, "search_items", query="Mystery Box")["items"][0]

    loot_json = json.dumps(item["loot"])
    assert "SECRET DIARY" not in loot_json
    assert "secret" not in loot_json.lower()
    assert "diary" not in loot_json.lower()

    # No item id should appear in the masked row
    masked_row = item["loot"][0]
    assert "id" not in masked_row
    assert "item_id" not in masked_row
    assert masked_row["label"] == "???"


def test_search_items_non_container_has_no_loot(mcp, gm_connection, club):
    """Non-container rows have is_container: false and no loot key."""
    secret = gm_connection[1]

    Item.objects.create(club=club, name="Plain Sword", value_cp=1500)

    item = sc(mcp, secret, "search_items", query="Plain Sword")["items"][0]

    assert item["is_container"] is False
    assert "loot" not in item or item.get("loot") == []


def test_search_items_other_club_container_not_included(
    mcp, gm_connection, other_club_gm_connection, club, other_club
):
    """Other club's container never appears in results."""
    secret = gm_connection[1]

    # Create container in other club
    other_container = make_container(other_club, "Foreign Chest")
    foreign_gold = Item.objects.create(club=other_club, name="Foreign Gold", value_cp=100)
    add_slot(other_container, [(foreign_gold, 1, 1, 1)], chance_pct=100)

    # Search in this club
    result = sc(mcp, secret, "search_items")
    names = {item["name"] for item in result["items"]}
    assert "Foreign Chest" not in names


def test_search_items_prefetch_avoids_n_plus_one(mcp, gm_connection, club):
    """Only one query per container for slots/options (cap limit <= 100 acceptable)."""
    secret = gm_connection[1]

    # Create 5 containers
    for i in range(5):
        container = make_container(club, f"Box {i}")
        item = Item.objects.create(club=club, name=f"Item {i}", value_cp=100)
        add_slot(container, [(item, 1, 1, 1)], chance_pct=100)

    with CaptureQueriesContext(connection) as ctx:
        result = sc(mcp, secret, "search_items", limit=20)
        containers = [item for item in result["items"] if item["is_container"]]
        assert len(containers) == 5
        for item in containers:
            assert "loot" in item

    # Should be: 1 query for items, 1 for slots, 1 for options = 3 queries
    # (Plus possibly 1 for club, but that's cached)
    select_queries = [
        q for q in ctx.captured_queries if q["sql"].strip().upper().startswith("SELECT")
    ]
    # At most 5 SELECT queries (items + slots + options + maybe club + session)
    assert len(select_queries) <= 5, (
        f"Too many queries: {len(select_queries)}: {[q['sql'] for q in select_queries]}"
    )


# ---------------------------------------------------------------------------
# Batch and propose tools: no loot leak
# ---------------------------------------------------------------------------


def test_propose_awards_container_carries_only_item_name(mcp, gm_connection, club, character):
    """propose_awards batch output carries only item_name, no loot."""
    secret = gm_connection[1]

    container = make_container(club, "Reward Chest")
    item = Item.objects.create(club=club, name="Reward Item", value_cp=100)
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100)

    # Propose an award with the container (requires idempotency_key)
    result = sc(
        mcp,
        secret,
        "propose_awards",
        lines=[
            {
                "character_id": character.pk,
                "item_id": container.pk,
                "quantity": 1,
                "note": "Quest reward",
            }
        ],
        idempotency_key="test-container-leak-1",
    )

    # Result is the serialized batch directly (not wrapped in "batch")
    lines = result["lines"]
    assert len(lines) == 1
    line = lines[0]
    assert "item_name" in line
    assert line["item_name"] == "Reward Chest"
    assert "loot" not in line
    assert "is_container" not in line


# ---------------------------------------------------------------------------
# Source guard: agent_access code must not read slots directly
# ---------------------------------------------------------------------------


# Direct reads of container slots. Agent code must call loot_preview() instead.
# (".options" is not listed: PreviewRow.options is loot_preview output, and slot
# options are reachable only through .slots or the slot models.)
_SLOT_READ = re.compile(r"\.(slots|prefetched_slots)\b|\bContainerSlot(Option)?\b")
# tools_lookup.py may name the slot models only to build the Prefetch that
# loot_preview() then consumes. It must still never read .slots itself.
_PREFETCH_ONLY = {"tools_lookup.py": re.compile(r"\bContainerSlot(Option)?\b")}
_AGENT_ACCESS = Path(__file__).resolve().parents[1]


def _slot_violations(path: Path, text: str) -> list[str]:
    allowed = _PREFETCH_ONLY.get(path.name)
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]
        for match in _SLOT_READ.finditer(code):
            if allowed and allowed.fullmatch(match.group(0)):
                continue
            found.append(f"{path.name}:{n}: {match.group(0)}")
    return found


def test_agent_access_no_direct_slot_access():
    """Non-test code under agent_access/ never reads container slots directly."""
    violations = []
    for path in _AGENT_ACCESS.rglob("*.py"):
        rel = path.relative_to(_AGENT_ACCESS).parts
        if rel[0] in {"tests", "migrations"}:
            continue
        violations += _slot_violations(path, path.read_text())
    assert not violations, "Use loot_preview() instead:\n" + "\n".join(violations)


@pytest.mark.parametrize(
    "snippet",
    [
        "rows = item.slots.all()",
        "rows = item.prefetched_slots",
        "opts = ContainerSlotOption.objects.all()",
        "from items.models import ContainerSlot",
        "from items.containers import loot_preview\nrows = item.slots.all()",
    ],
)
def test_slot_guard_catches_direct_reads(snippet):
    """The guard flags direct reads, even in a file that also imports loot_preview."""
    assert _slot_violations(Path("tools_new.py"), snippet)


def test_slot_guard_lookup_may_only_name_models():
    """tools_lookup.py may name the slot models but not read slots."""
    path = Path("tools_lookup.py")
    assert not _slot_violations(path, "Prefetch('slots', queryset=ContainerSlot.objects)")
    assert _slot_violations(path, "rows = item.slots.all()")


# ---------------------------------------------------------------------------
# loot_preview masking tests (unit level)
# ---------------------------------------------------------------------------


def test_loot_preview_masks_unknown_for_player(club):
    """loot_preview with viewer_can_see_unknown=False masks unknown slots."""
    container = make_container(club, "Test")
    secret_item = Item.objects.create(club=club, name="Hidden Item", value_cp=1)
    add_slot(container, [(secret_item, 1, 1, 1)], chance_pct=100, unknown=True)

    preview = loot_preview(container, viewer_can_see_unknown=False)
    assert len(preview) == 1
    row = preview[0]
    assert row.masked is True
    assert row.label == "???"
    assert row.item is None
    assert row.qty_min is None
    assert row.qty_max is None
    assert row.options == ()


def test_loot_preview_reveals_unknown_for_gm(club):
    """loot_preview with viewer_can_see_unknown=True reveals unknown slots."""
    container = make_container(club, "Test")
    secret_item = Item.objects.create(club=club, name="Hidden Item", value_cp=1)
    add_slot(container, [(secret_item, 1, 1, 1)], chance_pct=100, unknown=True)

    preview = loot_preview(container, viewer_can_see_unknown=True)
    row = preview[0]
    assert row.masked is False
    assert row.item == secret_item
    assert row.label == "Hidden Item"


def test_loot_preview_fixed_ranged_percent_one_of(club):
    """All row types appear with correct numbers."""
    container = make_container(club, "Test")
    item1 = Item.objects.create(club=club, name="Fixed", value_cp=1)
    item2 = Item.objects.create(club=club, name="Ranged", value_cp=1)
    item3 = Item.objects.create(club=club, name="Percent", value_cp=1)
    item4 = Item.objects.create(club=club, name="Option A", value_cp=1)
    item5 = Item.objects.create(club=club, name="Option B", value_cp=1)

    add_slot(container, [(item1, 1, 1, 1)], chance_pct=100, position=0)
    add_slot(container, [(item2, 2, 5, 1)], chance_pct=100, position=1)
    add_slot(container, [(item3, 1, 1, 1)], chance_pct=25, position=2)
    add_slot(container, [(item4, 1, 1, 3), (item5, 1, 1, 1)], chance_pct=100, position=3)

    preview = loot_preview(container, viewer_can_see_unknown=True)
    assert len(preview) == 4

    # Fixed
    assert preview[0].label == "Fixed"
    assert preview[0].qty_min == 1 and preview[0].qty_max == 1

    # Ranged
    assert preview[1].label == "Ranged"
    assert preview[1].qty_min == 2 and preview[1].qty_max == 5

    # Percent
    assert preview[2].label == "Percent"
    assert preview[2].chance_pct == 25

    # One of
    assert preview[3].label == "One of"
    assert preview[3].item is None
    opt_labels = {o.label for o in preview[3].options}
    assert opt_labels == {"Option A", "Option B"}
    weights = {o.label: o.weight_pct for o in preview[3].options}
    assert weights["Option A"] == 75
    assert weights["Option B"] == 25
