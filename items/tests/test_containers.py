"""Tests for the container contract (C0)."""

import json
import random
import sqlite3

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from items.containers import (
    PreviewOption,
    loot_preview,
    roll_container,
    validate_container_config,
)
from items.models import ContainerOpening, ContainerSlot, ContainerSlotOption, Item
from items.services import item_is_referenced
from items.tests.factories import add_slot, make_container
from ledger.models import AppendOnlyError, LedgerEntry, LedgerLine
from ledger.services import Line, record

pytestmark = [pytest.mark.story("C0"), pytest.mark.django_db]


class StubRNG:
    """Deterministic rng that consumes a pre-defined list of draws."""

    def __init__(self, draws):
        self.draws = list(draws)

    def randint(self, a, b):
        return self.draws.pop(0)

    def randrange(self, n):
        return self.draws.pop(0)


# ---------------------------------------------------------------------------
# roll_container
# ---------------------------------------------------------------------------


def test_roll_fixed_slot_always_hits(diplomats_pack):
    roll = roll_container(diplomats_pack, rng=random.Random(1))
    first = roll.slots[0]
    assert first.hit is True
    assert first.qty == 1
    assert first.item_id is not None


def test_roll_range_stays_within_min_max(diplomats_pack):
    seen = set()
    for seed in range(200):
        roll = roll_container(diplomats_pack, rng=random.Random(seed))
        flask = roll.slots[1]
        assert flask.hit is True
        assert 1 <= flask.qty <= 2
        seen.add(flask.qty)
    assert seen == {1, 2}


def test_roll_chance_100_never_draws(diplomats_pack):
    calls = []

    class CountingRNG:
        def randint(self, a, b):
            calls.append((a, b))
            return 1

        def randrange(self, n):
            calls.append(("randrange", n))
            return 0

    roll = roll_container(diplomats_pack, rng=CountingRNG())
    assert roll.slots[0].hit is True
    # Only the 50% perfume slot draws a chance check; every 100% slot hits.
    chance_draws = [c for c in calls if c == (1, 100)]
    assert len(chance_draws) == 1


def test_roll_chance_edge_hit_and_miss(club):
    item = Item.objects.create(club=club, name="Rope", value_cp=1)
    container = make_container(club)
    add_slot(container, [(item, 1, 1, 1)], chance_pct=50)
    # Draw below chance -> hit; draw above chance -> miss.
    assert roll_container(container, rng=StubRNG([1])).slots[0].hit is True
    assert roll_container(container, rng=StubRNG([100])).slots[0].hit is False


def test_roll_weighted_distribution(diplomats_pack):
    pack = diplomats_pack
    wax = Item.objects.get(club=pack.club, name="Sealing wax")
    wax_hits = 0
    trials = 300
    for seed in range(trials):
        weighted = roll_container(pack, rng=random.Random(seed)).slots[3]
        assert weighted.hit is True
        if weighted.item_id == wax.pk:
            wax_hits += 1
    share = wax_hits / trials
    assert 0.65 < share < 0.85  # weight 3 of 4


def test_roll_weighted_exact_pick_via_scripted_randrange(diplomats_pack):
    pack = diplomats_pack
    wax = Item.objects.get(club=pack.club, name="Sealing wax")
    soap = Item.objects.get(club=pack.club, name="Soap")
    # total weight 4; draw 3 -> soap, draw 0 -> wax.
    assert roll_container(pack, rng=StubRNG([1, 1, 3])).slots[3].item_id == soap.pk
    assert roll_container(pack, rng=StubRNG([1, 1, 0])).slots[3].item_id == wax.pk


def test_roll_slot_with_no_options_is_miss(club):
    container = make_container(club)
    add_slot(container, [], chance_pct=100)
    outcome = roll_container(container, rng=random.Random(1)).slots[0]
    assert outcome.hit is False
    assert outcome.qty == 0
    assert outcome.item_id is None


def test_roll_lines_merge_by_item(club):
    rope = Item.objects.create(club=club, name="Rope", value_cp=1)
    container = make_container(club)
    add_slot(container, [(rope, 1, 1, 1)], position=0)
    add_slot(container, [(rope, 2, 2, 1)], position=1)
    roll = roll_container(container, rng=random.Random(1))
    assert roll.lines[rope] == 3
    assert list(roll.lines.keys()) == [rope]


def test_roll_same_seed_same_roll(diplomats_pack):
    a = roll_container(diplomats_pack, rng=random.Random(42))
    b = roll_container(diplomats_pack, rng=random.Random(42))
    assert a.as_result() == b.as_result()


def test_roll_is_pure(diplomats_pack):
    before_entries = LedgerEntry.objects.count()
    before_lines = LedgerLine.objects.count()
    before_openings = ContainerOpening.objects.count()
    with CaptureQueriesContext(connection) as ctx:
        roll_container(diplomats_pack, rng=random.Random(7))
    write_prefixes = ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE")
    write_queries = [
        q["sql"]
        for q in ctx.captured_queries
        if q["sql"].lstrip().upper().startswith(write_prefixes)
    ]
    assert not write_queries, write_queries
    assert LedgerEntry.objects.count() == before_entries
    assert LedgerLine.objects.count() == before_lines
    assert ContainerOpening.objects.count() == before_openings


def test_roll_as_result_is_json_serialisable(diplomats_pack):
    roll = roll_container(diplomats_pack, rng=random.Random(7))
    payload = json.dumps(roll.as_result())
    assert isinstance(payload, str)
    data = json.loads(payload)
    assert len(data) == 5  # one row per slot
    keys = {"slot_id", "position", "hit", "option_id", "item_id", "qty"}
    assert all(set(row) == keys for row in data)
    for row, outcome in zip(data, roll.slots, strict=True):
        assert row["option_id"] == outcome.option_id
        if row["hit"]:
            assert row["option_id"] is not None


# ---------------------------------------------------------------------------
# loot_preview
# ---------------------------------------------------------------------------


def test_preview_fixed_range_percent_one_of_rows(diplomats_pack):
    rows = loot_preview(diplomats_pack, viewer_can_see_unknown=True)
    assert len(rows) == 5
    club = diplomats_pack.club
    # Fixed: fine clothes x1
    assert rows[0].item is not None
    assert rows[0].label == "Fine clothes"
    assert rows[0].qty_min == 1 and rows[0].qty_max == 1
    assert rows[0].chance_pct == 100
    assert rows[0].options == ()
    assert rows[0].masked is False
    # Ranged: flask of oil 1-2
    assert rows[1].label == "Flask of oil"
    assert rows[1].qty_min == 1 and rows[1].qty_max == 2
    # Percent: vial of perfume 50%
    assert rows[2].chance_pct == 50
    # One of: sealing wax (75) / soap (25)
    assert rows[3].item is None
    assert rows[3].label == "One of"
    assert rows[3].options == (
        PreviewOption(
            item=Item.objects.get(club=club, name="Sealing wax"),
            label="Sealing wax",
            qty_min=1,
            qty_max=1,
            weight_pct=75,
        ),
        PreviewOption(
            item=Item.objects.get(club=club, name="Soap"),
            label="Soap",
            qty_min=1,
            qty_max=1,
            weight_pct=25,
        ),
    )
    # Unknown slot keeps the flag for a GM.
    assert rows[4].unknown is True


def test_preview_masks_unknown_for_player(diplomats_pack):
    rows = loot_preview(diplomats_pack, viewer_can_see_unknown=False)
    masked = rows[4]
    assert masked.masked is True
    assert masked.item is None
    assert masked.label == "???"
    assert masked.qty_min is None and masked.qty_max is None
    assert masked.options == ()
    assert masked.chance_pct == 100
    assert masked.unknown is True
    assert "Sealed letter" not in repr(rows)


def test_preview_unknown_visible_to_gm(diplomats_pack):
    rows = loot_preview(diplomats_pack, viewer_can_see_unknown=True)
    letter = Item.objects.get(club=diplomats_pack.club, name="Sealed letter")
    assert rows[4].masked is False
    assert rows[4].item == letter
    assert rows[4].label == "Sealed letter"


# ---------------------------------------------------------------------------
# validate_container_config
# ---------------------------------------------------------------------------


def test_validate_clean_pack_passes(diplomats_pack):
    validate_container_config(diplomats_pack)  # does not raise


def test_validate_self_cycle_rejected(club):
    container = make_container(club)
    add_slot(container, [container], chance_pct=100)
    with pytest.raises(ValidationError) as exc:
        validate_container_config(container)
    assert "contains itself" in str(exc.value)


def test_validate_ab_cycle_rejected(club):
    a = make_container(club, "A")
    b = make_container(club, "B")
    add_slot(a, [b], chance_pct=100)
    add_slot(b, [a], chance_pct=100)
    with pytest.raises(ValidationError):
        validate_container_config(a)
    with pytest.raises(ValidationError):
        validate_container_config(b)


def test_validate_depth_three_ok(club):
    a = make_container(club, "A")
    b = make_container(club, "B")
    c = make_container(club, "C")
    add_slot(b, [a], chance_pct=100)
    add_slot(c, [b], chance_pct=100)
    validate_container_config(c)  # A in B in C is ok


def test_validate_depth_four_fails_down(club):
    a = make_container(club, "A")
    b = make_container(club, "B")
    c = make_container(club, "C")
    d = make_container(club, "D")
    add_slot(b, [a], chance_pct=100)
    add_slot(c, [b], chance_pct=100)
    add_slot(d, [c], chance_pct=100)
    with pytest.raises(ValidationError):
        validate_container_config(d)  # four levels down


def test_validate_depth_four_fails_up(club):
    a = make_container(club, "A")
    b = make_container(club, "B")
    c = make_container(club, "C")
    d = make_container(club, "D")
    add_slot(b, [a], chance_pct=100)
    add_slot(c, [b], chance_pct=100)
    add_slot(d, [c], chance_pct=100)
    with pytest.raises(ValidationError):
        validate_container_config(a)  # four levels up through parents


def test_validate_empty_slot_rejected(club):
    container = make_container(club)
    add_slot(container, [], chance_pct=100)
    with pytest.raises(ValidationError):
        validate_container_config(container)


def test_validate_cross_club_item_rejected(club, other_club):
    container = make_container(club)
    foreign = Item.objects.create(club=other_club, name="Foreign", value_cp=1)
    add_slot(container, [(foreign, 1, 1, 1)], chance_pct=100)
    with pytest.raises(ValidationError):
        validate_container_config(container)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


def test_constraints_reject_invalid_values(club):
    container = make_container(club)
    good_item = Item.objects.create(club=club, name="Good", value_cp=1)

    slot = ContainerSlot.objects.create(container=container, chance_pct=50)

    def expect_integrity_error(fn):
        with pytest.raises((IntegrityError, sqlite3.IntegrityError)):
            with transaction.atomic():
                fn()

    expect_integrity_error(lambda: ContainerSlot.objects.create(container=container, chance_pct=0))
    expect_integrity_error(
        lambda: ContainerSlot.objects.create(container=container, chance_pct=101)
    )
    slot.chance_pct = 0
    expect_integrity_error(slot.save)

    expect_integrity_error(
        lambda: ContainerSlotOption.objects.create(
            slot=slot, item=good_item, qty_min=0, qty_max=1, weight=1
        )
    )
    expect_integrity_error(
        lambda: ContainerSlotOption.objects.create(
            slot=slot, item=good_item, qty_min=2, qty_max=1, weight=1
        )
    )
    expect_integrity_error(
        lambda: ContainerSlotOption.objects.create(
            slot=slot, item=good_item, qty_min=1, qty_max=1, weight=0
        )
    )


def test_container_opening_is_write_once(club, character):
    entry = LedgerEntry.objects.create(
        club=club,
        character=character,
        kind=LedgerEntry.Kind.OPENED,
        note="test",
    )
    container = make_container(club)
    opening = ContainerOpening.objects.create(
        entry=entry, container=container, character=character, result={}
    )
    with pytest.raises(AppendOnlyError):
        opening.save()
    with pytest.raises(AppendOnlyError):
        opening.delete()


def test_container_opening_marks_item_referenced(club):
    rope = Item.objects.create(club=club, name="Rope", value_cp=1)
    container = make_container(club)
    add_slot(container, [(rope, 1, 1, 1)], chance_pct=100)
    assert item_is_referenced(rope) is True


# ---------------------------------------------------------------------------
# ledger kind
# ---------------------------------------------------------------------------


def test_opened_kind_exists_and_records(club, character, item):
    assert LedgerEntry.Kind.OPENED.value == "opened"
    assert "opened" in LedgerEntry.Kind.values
    entry = record(
        character=character,
        kind="opened",
        lines=[Line(item=item, quantity=1)],
        note="opened a pack",
    )
    assert entry.kind == "opened"
    assert entry.character == character
    assert entry.note == "opened a pack"
    assert entry.date == timezone.localdate()
