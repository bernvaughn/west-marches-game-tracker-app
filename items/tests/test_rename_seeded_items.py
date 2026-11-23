"""Tests for the rename_seeded_items catch-up command (U152)."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import Membership, User
from items.models import ContainerSlot, ContainerSlotOption, Item
from items.seed_names import MAP_CASE, SCROLL_CASE
from items.services_rename import get_related_objects_to_item
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import Line, item_quantities, record
from player_characters.models import Character
from quests.models import QuestRequirement, QuestReward
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassLine,
    StartingEquipmentTemplate,
)

pytestmark = [pytest.mark.django_db]


def run(club, apply=False):
    out = StringIO()
    args = ["rename_seeded_items", "--club", club.slug]
    if apply:
        args.append("--apply")
    call_command(*args, stdout=out)
    return out.getvalue()


def make_character(club, name):
    user = User.objects.create_user(f"{name.lower()}@example.com", password="pw", display_name=name)
    membership = Membership.objects.create(user=user, club=club)
    return Character.objects.create(club=club, owner=membership, name=name)


def snapshot():
    return (
        list(Item.objects.order_by("pk").values()),
        LedgerEntry.objects.count(),
    )


@pytest.fixture
def lute_old(club):
    """Old name 'Lute' item."""
    return Item.objects.create(club=club, name="Lute", value_cp=3500, symbol="🎵")


@pytest.fixture
def flute_old(club):
    return Item.objects.create(club=club, name="Flute", value_cp=200, symbol="🎵")


@pytest.fixture
def map_case_old(club):
    return Item.objects.create(club=club, name="Case, Map or Scroll", value_cp=100, symbol="🗺️")


@pytest.fixture
def map_or_scroll_case_old(club):
    return Item.objects.create(club=club, name="Map or Scroll Case", value_cp=100, symbol="📜")


@pytest.fixture
def diplomats_pack(club):
    return Item.objects.create(club=club, name="Diplomat's Pack", value_cp=3900, is_container=True)


def test_dry_run_changes_nothing(club, lute_old):
    before = snapshot()
    out = run(club)
    assert "DRY RUN" in out
    assert snapshot() == before
    lute_old.refresh_from_db()
    assert lute_old.name == "Lute"


def test_apply_renames_in_place_keeps_ids(club, lute_old, flute_old):
    """Renamed items keep pk; shop lines, quests, containers, inventories stay linked."""
    char = make_character(club, "Aria")
    record(char, "award", [Line(item=lute_old, quantity=1), Line(item=flute_old, quantity=2)])

    # Shop stock
    from shops.models import Shop, ShopStock

    shop = Shop.objects.create(club=club, name="Test Shop")
    ShopStock.objects.create(shop=shop, item=lute_old, quantity=5)

    # Quest requirement/reward
    from quests.models import Quest

    quest = Quest.objects.create(club=club, name="Test Quest")
    QuestRequirement.objects.create(quest=quest, item=lute_old, quantity=1)
    QuestReward.objects.create(quest=quest, item=flute_old, quantity=1)

    # Container slot option
    container = Item.objects.create(club=club, name="Test Bag", is_container=True)
    slot = ContainerSlot.objects.create(container=container, chance_pct=100)
    ContainerSlotOption.objects.create(slot=slot, item=lute_old, qty_min=1, qty_max=1)

    # Starting equipment line
    template = StartingEquipmentTemplate.objects.create(club=club, name="T", is_active=True)
    from character_options.models import CharacterClass
    from starting_equipment.models import StartingEquipmentClassEntry

    class_opt = CharacterClass.objects.create(club=club, name="TestClass")
    entry = StartingEquipmentClassEntry.objects.create(template=template, class_option=class_opt)
    StartingEquipmentClassLine.objects.create(class_entry=entry, item=lute_old, quantity=1)

    lute_pk = lute_old.pk
    flute_pk = flute_old.pk

    out = run(club, apply=True)
    assert "Renames" in out

    lute_old.refresh_from_db()
    flute_old.refresh_from_db()
    assert lute_old.pk == lute_pk
    assert flute_old.pk == flute_pk
    assert lute_old.name == "Lute (Musical Instrument)"
    assert flute_old.name == "Flute (Musical Instrument)"

    # Inventory still linked
    assert item_quantities(char)[lute_pk] == 1
    assert item_quantities(char)[flute_pk] == 2

    # Shop stock still linked
    stock = ShopStock.objects.get(shop=shop, item=lute_old)
    assert stock.quantity == 5

    # Quest rows still linked
    assert QuestRequirement.objects.filter(quest=quest, item=lute_old).exists()
    assert QuestReward.objects.filter(quest=quest, item=flute_old).exists()

    # Container slot option still linked
    assert ContainerSlotOption.objects.filter(slot=slot, item=lute_old).exists()

    # Starting equipment line still linked
    assert StartingEquipmentClassLine.objects.filter(class_entry=entry, item=lute_old).exists()


def test_edited_item_left_alone(club):
    """Item with modified value/symbol/description is skipped, listed as left alone."""
    # Create item with different value than seed (seed says 3500)
    edited_lute = Item.objects.create(club=club, name="Lute", value_cp=5000, symbol="🎵")

    out = run(club, apply=True)
    assert "Left alone" in out
    assert "edited" in out.lower() or "value" in out.lower()

    edited_lute.refresh_from_db()
    assert edited_lute.name == "Lute"  # Unchanged
    assert edited_lute.value_cp == 5000


def test_duplicate_instruments_merge_with_ledger(club):
    """Two old records for same instrument merge, one ledger entry per holder, FKs repointed."""
    # Two "Lute" items (simulating Bard's "Lute" and Entertainer's "Musical Instrument (Lute)")
    lute1 = Item.objects.create(club=club, name="Lute", value_cp=3500, symbol="🎵")
    lute2 = Item.objects.create(
        club=club, name="Musical Instrument (Lute)", value_cp=3500, symbol="🎵"
    )

    char1 = make_character(club, "Aria")
    char2 = make_character(club, "Borin")
    record(char1, "award", [Line(item=lute1, quantity=1)])
    record(char2, "award", [Line(item=lute2, quantity=2)])

    # FKs on both
    from shops.models import Shop, ShopStock

    shop = Shop.objects.create(club=club, name="Test Shop")
    ShopStock.objects.create(shop=shop, item=lute1, quantity=3)
    ShopStock.objects.create(shop=shop, item=lute2, quantity=2)

    # Quest on lute2
    from quests.models import Quest

    quest = Quest.objects.create(club=club, name="Test Quest")
    QuestRequirement.objects.create(quest=quest, item=lute2, quantity=1)

    out = run(club, apply=True)
    assert "Merges" in out

    # Only one item remains, with lower pk (lute1)
    lute_items = list(Item.objects.filter(club=club, name="Lute (Musical Instrument)"))
    assert len(lute_items) == 1
    survivor = lute_items[0]
    assert survivor.pk == lute1.pk

    # Quantities merged: Aria had 1, Borin had 2 -> both now on survivor
    assert item_quantities(char1)[survivor.pk] == 1
    assert item_quantities(char2)[survivor.pk] == 2

    # Ledger entries created
    adjustments = LedgerEntry.objects.filter(kind="adjustment")
    assert adjustments.count() == 1  # Only Borin held lute2 (source)

    # ShopStock merged (3 + 2 = 5)
    stock = ShopStock.objects.get(shop=shop, item=survivor)
    assert stock.quantity == 5

    # QuestRequirement repointed
    assert QuestRequirement.objects.filter(quest=quest, item=survivor).exists()
    assert not QuestRequirement.objects.filter(quest=quest, item=lute2).exists()

    # lute2 retired
    lute2.refresh_from_db()
    assert lute2.retired


def test_every_foreign_key_repointed(club):
    """Test that iterates Item._meta.related_objects and asserts each was repointed."""
    # Create source and target items
    source = Item.objects.create(club=club, name="Lute", value_cp=3500, symbol="🎵")
    target = Item.objects.create(
        club=club, name="Lute (Musical Instrument)", value_cp=3500, symbol="🎵"
    )

    char = make_character(club, "Aria")
    record(char, "award", [Line(item=source, quantity=1)])

    # Create one instance of each FK relation (except LedgerLine which is append-only)
    from shops.models import Shop, ShopStock

    shop = Shop.objects.create(club=club, name="Test Shop")
    ShopStock.objects.create(shop=shop, item=source, quantity=1)

    from quests.models import Quest

    quest = Quest.objects.create(club=club, name="Test Quest")
    QuestRequirement.objects.create(quest=quest, item=source, quantity=1)
    QuestReward.objects.create(quest=quest, item=source, quantity=1)

    container = Item.objects.create(club=club, name="Test Bag", is_container=True)
    slot = ContainerSlot.objects.create(container=container, chance_pct=100)
    ContainerSlotOption.objects.create(slot=slot, item=source, qty_min=1, qty_max=1)

    template = StartingEquipmentTemplate.objects.create(club=club, name="T", is_active=True)
    from character_options.models import Background, CharacterClass
    from starting_equipment.models import (
        StartingEquipmentBackgroundEntry,
        StartingEquipmentClassEntry,
    )

    class_opt = CharacterClass.objects.create(club=club, name="TestClass")
    bg_opt = Background.objects.create(club=club, name="TestBackground")
    class_entry = StartingEquipmentClassEntry.objects.create(
        template=template, class_option=class_opt
    )
    bg_entry = StartingEquipmentBackgroundEntry.objects.create(
        template=template, background_option=bg_opt
    )
    StartingEquipmentClassLine.objects.create(class_entry=class_entry, item=source, quantity=1)
    StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry, item=source, quantity=1
    )

    MagicItemStartingOption.objects.create(template=template, item=source, max_per_character=1)

    from player_characters.models import JunkMark
    from starting_equipment.models import StartingEquipmentRequest

    StartingEquipmentRequest.objects.create(
        club=club, character=char, item=source, quantity=1, status="pending"
    )
    JunkMark.objects.create(character=char, item=source, quantity=1)

    from accounts.models import User
    from agent_access.models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine

    conn_user = User.objects.create_user("conn@example.com", password="pw")
    connection = AgentConnection.objects.create(club=club, user=conn_user, label="Test Connection")
    batch = ProposedBatch.objects.create(
        club=club,
        connection=connection,
        user=conn_user,
        status=ProposedBatch.Status.PENDING,
        date="2024-01-01",
        idempotency_key="test",
    )
    ProposedItem.objects.create(batch=batch, club=club, name="Test", approved_item=source)
    ProposedLine.objects.create(batch=batch, character=char, item=source, quantity=1)

    from downtime.models import DowntimeAction, DowntimeEntry, DowntimeEntryItem

    dt_action = DowntimeAction.objects.create(club=club, name="Test Action", cost=1)
    dt_entry = DowntimeEntry.objects.create(action=dt_action, label="Test Entry", weight=1)
    DowntimeEntryItem.objects.create(entry=dt_entry, item=source, quantity=1)

    # Run merge
    run(club, apply=True)

    # After merge, source (lower pk) survives and gets renamed to target_name
    # target gets retired. So FKs should point to source (the survivor).
    survivor = source
    merged = target

    # Verify every relation from Item._meta.related_objects (except LedgerLine) was repointed
    # Note: "slots" (ContainerSlot.container) and "openings" (ContainerOpening.container)
    # point to the container, not the content item. Since we didn't create any
    # ContainerSlot/ContainerOpening where container=source, skip them.
    relations = get_related_objects_to_item()
    for rel in relations:
        accessor = rel.get_accessor_name()
        if accessor in ("ledgerline_set", "slots", "openings"):
            continue  # LedgerLine is append-only; slots/openings point to container not content
        model = rel.related_model
        fk_field = rel.field.name

        # Check that no rows point to merged (retired) item
        count = model.objects.filter(**{fk_field: merged}).count()
        assert count == 0, (
            f"{model.__name__}.{fk_field} still has {count} rows pointing to merged item"
        )

        # Check that rows now point to survivor
        survivor_count = model.objects.filter(**{fk_field: survivor}).count()
        assert survivor_count > 0, f"{model.__name__}.{fk_field} has no rows pointing to survivor"

    # Also check ProposedItem.approved_item (related_name="+")
    assert not ProposedItem.objects.filter(approved_item=merged).exists()
    assert ProposedItem.objects.filter(approved_item=survivor).exists()


def test_negative_holder_refuses(club):
    """Holder with negative net refuses whole run, nothing written."""
    from django.utils import timezone

    lute1 = Item.objects.create(club=club, name="Lute", value_cp=3500, symbol="🎵")
    lute2 = Item.objects.create(
        club=club, name="Musical Instrument (Lute)", value_cp=3500, symbol="🎵"
    )

    char = make_character(club, "Aria")
    record(char, "award", [Line(item=lute1, quantity=1), Line(item=lute2, quantity=1)])
    # Create negative net on lute2 (source being merged) via direct ledger entry
    entry = LedgerEntry.objects.create(
        character=char,
        club=club,
        kind=LedgerEntry.Kind.ADJUSTMENT,
        note="test",
        date=timezone.localdate(),
    )
    LedgerLine.objects.create(entry=entry, item=lute2, quantity=-2)  # net -1 on lute2

    before = snapshot()
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("rename_seeded_items", "--club", club.slug, "--apply", stdout=out)
    assert snapshot() == before
    assert "negative" in out.getvalue().lower()
    assert "Aria" in out.getvalue()

    lute1.refresh_from_db()
    lute2.refresh_from_db()
    assert lute1.name == "Lute"
    assert lute2.name == "Musical Instrument (Lute)"


def test_net_zero_holder_skipped(club):
    """Holder with net 0 is skipped, no ledger entry."""
    lute1 = Item.objects.create(club=club, name="Lute", value_cp=3500, symbol="🎵")
    Item.objects.create(club=club, name="Musical Instrument (Lute)", value_cp=3500, symbol="🎵")

    char = make_character(club, "Aria")
    record(char, "award", [Line(item=lute1, quantity=1)])
    record(char, "consumed", [Line(item=lute1, quantity=-1)])  # net 0

    out = run(club, apply=True)
    assert "Merges" in out

    # No adjustment entry for this merge (net 0 holder skipped)
    adjustments = LedgerEntry.objects.filter(kind="adjustment")
    # Only the merge itself might create entries for other holders, but this char has net 0
    # Actually the merge creates entries per source item per holder with net > 0
    # Since net is 0, no entry should be created
    assert adjustments.count() == 0

    # Survivor has the item
    survivor = Item.objects.get(club=club, name="Lute (Musical Instrument)")
    assert item_quantities(char).get(survivor.pk, 0) == 0


def test_map_case_split(club, map_case_old, map_or_scroll_case_old, diplomats_pack):
    """Both old case names merge to Map Case; Scroll Case created; Diplomat's Pack slots updated."""
    # Set up old Diplomat's Pack with fixed 2x "Map or Scroll Case"
    slot = ContainerSlot.objects.create(container=diplomats_pack, chance_pct=100, position=1)
    old_case = map_or_scroll_case_old
    ContainerSlotOption.objects.create(slot=slot, item=old_case, qty_min=2, qty_max=2, weight=1)

    out = run(club, apply=True)
    assert "Splits" in out

    # Map Case exists
    map_case = Item.objects.get(club=club, name=MAP_CASE)
    assert map_case.pk == map_case_old.pk  # Lower ID wins

    # Scroll Case created
    scroll_case = Item.objects.get(club=club, name=SCROLL_CASE)
    assert scroll_case.value_cp == 100
    assert scroll_case.symbol == "📜"

    # Diplomat's Pack now has two choice slots
    pack = Item.objects.get(club=club, name="Diplomat's Pack")
    case_slots = [s for s in pack.slots.all() if s.options.count() == 2]
    assert len(case_slots) >= 2
    for s in case_slots[:2]:
        names = {o.item.name for o in s.options.all()}
        assert names == {MAP_CASE, SCROLL_CASE}


def test_edited_pack_left_alone(club, map_case_old, map_or_scroll_case_old, diplomats_pack):
    """Customized Diplomat's Pack slots not changed."""
    # Customized pack: already has choice slots
    map_case = Item.objects.create(club=club, name=MAP_CASE, value_cp=100, symbol="🗺️")
    scroll_case = Item.objects.create(club=club, name=SCROLL_CASE, value_cp=100, symbol="📜")

    slot1 = ContainerSlot.objects.create(container=diplomats_pack, chance_pct=100, position=1)
    ContainerSlotOption.objects.create(slot=slot1, item=map_case, qty_min=1, qty_max=1, weight=1)
    ContainerSlotOption.objects.create(slot=slot1, item=scroll_case, qty_min=1, qty_max=1, weight=1)

    slot2 = ContainerSlot.objects.create(container=diplomats_pack, chance_pct=100, position=2)
    ContainerSlotOption.objects.create(slot=slot2, item=map_case, qty_min=1, qty_max=1, weight=1)
    ContainerSlotOption.objects.create(slot=slot2, item=scroll_case, qty_min=1, qty_max=1, weight=1)

    out = run(club, apply=True)
    assert "left alone" in out.lower() or "already converted" in out.lower()

    # Slots unchanged
    pack = Item.objects.get(club=club, name="Diplomat's Pack")
    assert pack.slots.count() == 2


def test_second_run_nothing_to_do(
    club, lute_old, map_case_old, map_or_scroll_case_old, diplomats_pack
):
    """Second run prints 'nothing to do' and writes nothing."""
    # First run
    run(club, apply=True)
    before = snapshot()

    # Second run
    out = run(club, apply=True)
    assert "Nothing to do" in out
    assert snapshot() == before


def test_club_without_old_or_new_records_noop(club):
    """Club with neither old nor new records is a no-op."""
    out = run(club, apply=True)
    assert "Nothing to do" in out


def test_retired_items_handled(club):
    """Retired items are skipped or handled gracefully."""
    Item.objects.create(club=club, name="Lute", value_cp=3500, symbol="🎵", retired=True)
    active_lute = Item.objects.create(
        club=club, name="Musical Instrument (Lute)", value_cp=3500, symbol="🎵"
    )

    char = make_character(club, "Aria")
    record(char, "award", [Line(item=active_lute, quantity=1)])

    out = run(club, apply=True)
    # Retired item is ignored, active item is renamed in place
    assert "Renames" in out

    survivor = Item.objects.get(club=club, name="Lute (Musical Instrument)")
    assert survivor.pk == active_lute.pk
    assert item_quantities(char)[survivor.pk] == 1


def test_plain_tool_merge(club):
    """Plain tool items merge into artisan's tools variants."""
    plain_carpenter = Item.objects.create(
        club=club, name="Carpenter's Tools", value_cp=1000, symbol="🔨"
    )
    artisan_carpenter = Item.objects.create(
        club=club, name="Artisan's Tools (Carpenter's)", value_cp=1000, symbol="🔨"
    )

    char = make_character(club, "Aria")
    record(char, "award", [Line(item=plain_carpenter, quantity=1)])
    record(char, "award", [Line(item=artisan_carpenter, quantity=1)])

    out = run(club, apply=True)
    assert "Merges" in out

    survivor = Item.objects.get(club=club, name="Carpenter's Tools (Artisan's Tools)")
    assert survivor.pk == plain_carpenter.pk  # Lower ID wins
    assert item_quantities(char)[survivor.pk] == 2


def test_calligrapher_supplies_merge(club):
    """Calligrapher's Supplies merges into its artisan's tools variant."""
    plain = Item.objects.create(
        club=club, name="Calligrapher's Supplies", value_cp=1000, symbol="🖋️"
    )
    Item.objects.create(
        club=club, name="Artisan's Tools (Calligrapher's)", value_cp=1000, symbol="🖋️"
    )

    char = make_character(club, "Aria")
    record(char, "award", [Line(item=plain, quantity=1)])

    out = run(club, apply=True)
    assert "Merges" in out

    survivor = Item.objects.get(club=club, name="Calligrapher's Supplies (Artisan's Tools)")
    assert item_quantities(char)[survivor.pk] == 1


def test_arcane_focus_rename(club):
    """Arcane Focus items renamed to Variant (Kind) form."""
    Item.objects.create(club=club, name="Arcane Focus (Crystal)", value_cp=1000, symbol="🔮")
    Item.objects.create(club=club, name="Arcane Focus (Orb)", value_cp=2000, symbol="🔮")

    out = run(club, apply=True)
    assert "Renames" in out

    assert Item.objects.filter(club=club, name="Crystal (Arcane Focus)").exists()
    assert Item.objects.filter(club=club, name="Orb (Arcane Focus)").exists()
    assert not Item.objects.filter(club=club, name="Arcane Focus (Crystal)").exists()
    assert not Item.objects.filter(club=club, name="Arcane Focus (Orb)").exists()


def test_druidic_focus_rename(club):
    """Druidic Focus items renamed."""
    Item.objects.create(
        club=club, name="Druidic Focus (Sprig of Mistletoe)", value_cp=100, symbol="🌿"
    )
    Item.objects.create(club=club, name="Druidic Focus (Staff)", value_cp=500, symbol="🪄")

    out = run(club, apply=True)
    assert "Renames" in out

    assert Item.objects.filter(club=club, name="Sprig of Mistletoe (Druidic Focus)").exists()
    assert Item.objects.filter(club=club, name="Staff (Druidic Focus)").exists()


def test_holy_symbol_rename(club):
    """Holy Symbol items renamed."""
    Item.objects.create(club=club, name="Holy Symbol (Amulet)", value_cp=500, symbol="✝️")
    Item.objects.create(club=club, name="Holy Symbol (Emblem)", value_cp=500, symbol="✝️")

    out = run(club, apply=True)
    assert "Renames" in out

    assert Item.objects.filter(club=club, name="Amulet (Holy Symbol)").exists()
    assert Item.objects.filter(club=club, name="Emblem (Holy Symbol)").exists()


def test_gaming_set_rename(club):
    """Gaming Set items renamed."""
    Item.objects.create(club=club, name="Gaming Set (Dice)", value_cp=100, symbol="🎲")
    Item.objects.create(club=club, name="Gaming Set (Playing Cards)", value_cp=100, symbol="🎴")

    out = run(club, apply=True)
    assert "Renames" in out

    assert Item.objects.filter(club=club, name="Dice (Gaming Set)").exists()
    assert Item.objects.filter(club=club, name="Playing Cards (Gaming Set)").exists()


def test_drum_instrument_only_in_entertainer(club):
    """Drum is only in Entertainer's list, not Bard's."""
    Item.objects.create(club=club, name="Musical Instrument (Drum)", value_cp=600, symbol="🥁")
    Item.objects.create(club=club, name="Lute", value_cp=3500, symbol="🎵")

    out = run(club, apply=True)
    assert "Renames" in out

    assert Item.objects.filter(club=club, name="Drum (Musical Instrument)").exists()
    assert Item.objects.filter(club=club, name="Lute (Musical Instrument)").exists()

    # Only one Drum item, no merge with Bard items (Bard doesn't have Drum)
    drums = Item.objects.filter(club=club, name="Drum (Musical Instrument)")
    assert drums.count() == 1
