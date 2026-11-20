"""Tests for opening a container (slice B)."""

import random

import pytest

from items.containers import roll_container
from items.models import ContainerOpening, Item
from items.opening import OpenError, open_container, opening_view_model
from items.tests.factories import add_slot, make_container
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import Line, item_quantities, record

pytestmark = [pytest.mark.story("B"), pytest.mark.django_db]


class StubRNG:
    """Deterministic rng that consumes a pre-defined list of draws."""

    def __init__(self, draws):
        self.draws = list(draws)

    def randint(self, a, b):
        return self.draws.pop(0)

    def randrange(self, n):
        return self.draws.pop(0)


# ---------------------------------------------------------------------------
# open_container
# ---------------------------------------------------------------------------


def test_opened_entry_shape(club, character, diplomats_pack, club_admin):
    actor = club_admin
    record(character, "award", [Line(item=diplomats_pack, quantity=1)], actor=actor)
    roll = roll_container(diplomats_pack, rng=random.Random(42))
    before_entries = LedgerEntry.objects.count()
    before_openings = ContainerOpening.objects.count()

    opening = open_container(character, diplomats_pack, actor, rng=random.Random(42))

    assert isinstance(opening, ContainerOpening)
    assert opening.entry.pk is not None
    assert opening.entry.kind == "opened"
    assert opening.entry.character == character
    assert opening.entry.note == f"Opened {diplomats_pack.name}"
    assert opening.entry.created_by == actor
    assert opening.container == diplomats_pack
    assert opening.character == character
    assert opening.result == roll.as_result()

    lines = {line.item_id: line.quantity for line in opening.entry.lines.all()}
    assert lines[diplomats_pack.pk] == -1
    for item, qty in roll.lines.items():
        assert lines[item.pk] == qty
    assert len(lines) == 1 + len(roll.lines)  # container line plus one per rolled item
    assert not opening.entry.lines.filter(item__isnull=True).exists()  # no coin lines
    assert not opening.entry.lines.filter(coins__gt=0).exists()

    assert LedgerEntry.objects.count() == before_entries + 1
    assert ContainerOpening.objects.count() == before_openings + 1


def test_empty_roll_only_container_line(club, character, club_admin):
    rope = Item.objects.create(club=club, name="Rope", value_cp=1)
    container = make_container(club, name="Empty Box")
    add_slot(container, [(rope, 1, 1, 1)], chance_pct=1)
    record(character, "award", [Line(item=container, quantity=1)], actor=club_admin)

    roll = roll_container(container, rng=StubRNG([100]))
    assert not roll.slots[0].hit
    opening = open_container(character, container, club_admin, rng=StubRNG([100]))

    assert not opening.entry.lines.filter(quantity__gt=0).exists()
    lines = {line.item_id: line.quantity for line in opening.entry.lines.all()}
    assert lines == {container.pk: -1}
    assert opening.result == roll.as_result()


def test_inventory_after_open(club, character, diplomats_pack, club_admin):
    record(character, "award", [Line(item=diplomats_pack, quantity=1)], actor=club_admin)
    roll = roll_container(diplomats_pack, rng=random.Random(42))
    open_container(character, diplomats_pack, club_admin, rng=random.Random(42))

    quant = item_quantities(character)
    assert diplomats_pack.pk not in quant  # container consumed and absent
    for item, qty in roll.lines.items():
        assert quant[item.pk] == qty


def test_no_stock_raises_without_write(club, character, diplomats_pack, club_admin):
    before_e = LedgerEntry.objects.count()
    before_l = LedgerLine.objects.count()
    before_o = ContainerOpening.objects.count()

    with pytest.raises(OpenError):
        open_container(character, diplomats_pack, club_admin)

    assert LedgerEntry.objects.count() == before_e
    assert LedgerLine.objects.count() == before_l
    assert ContainerOpening.objects.count() == before_o


def test_non_container_refused(club, character, item, club_admin):
    before = LedgerEntry.objects.count()
    with pytest.raises(OpenError):
        open_container(character, item, club_admin)
    assert LedgerEntry.objects.count() == before
    assert ContainerOpening.objects.count() == 0


def test_cross_club_container_refused(club, character, other_club, club_admin):
    foreign = make_container(other_club, name="Foreign Box")
    before = LedgerEntry.objects.count()
    with pytest.raises(OpenError):
        open_container(character, foreign, club_admin)
    assert LedgerEntry.objects.count() == before
    assert ContainerOpening.objects.count() == 0


def test_container_without_slots_refused(club, character, club_admin):
    container = make_container(club, name="Empty Box")
    record(character, "award", [Line(item=container, quantity=1)], actor=club_admin)
    before_e = LedgerEntry.objects.count()
    before_l = LedgerLine.objects.count()
    before_o = ContainerOpening.objects.count()

    with pytest.raises(OpenError):
        open_container(character, container, club_admin)

    assert LedgerEntry.objects.count() == before_e
    assert LedgerLine.objects.count() == before_l
    assert ContainerOpening.objects.count() == before_o
    assert item_quantities(character).get(container.pk) == 1


def test_atomicity_rollback_on_create_failure(
    club, character, diplomats_pack, club_admin, monkeypatch
):
    record(character, "award", [Line(item=diplomats_pack, quantity=1)], actor=club_admin)
    before_e = LedgerEntry.objects.count()
    before_l = LedgerLine.objects.count()

    def boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ContainerOpening.objects, "create", boom)
    with pytest.raises(RuntimeError, match="boom"):
        open_container(character, diplomats_pack, club_admin)

    assert LedgerEntry.objects.count() == before_e
    assert LedgerLine.objects.count() == before_l
    assert item_quantities(character).get(diplomats_pack.pk) == 1


def test_double_open_one_copy_fails(club, character, diplomats_pack, club_admin):
    record(character, "award", [Line(item=diplomats_pack, quantity=1)], actor=club_admin)
    open_container(character, diplomats_pack, club_admin, rng=random.Random(42))

    before_e = LedgerEntry.objects.count()
    before_o = ContainerOpening.objects.count()

    with pytest.raises(OpenError):
        open_container(character, diplomats_pack, club_admin, rng=random.Random(42))

    assert LedgerEntry.objects.count() == before_e
    assert ContainerOpening.objects.count() == before_o
    assert diplomats_pack.pk not in item_quantities(character)


def test_double_open_two_copies_both_succeed(club, character, diplomats_pack, club_admin):
    record(character, "award", [Line(item=diplomats_pack, quantity=2)], actor=club_admin)
    open_container(character, diplomats_pack, club_admin, rng=random.Random(42))
    open_container(character, diplomats_pack, club_admin, rng=random.Random(42))

    assert diplomats_pack.pk not in item_quantities(character)  # net 0
    assert LedgerEntry.objects.filter(kind="opened").count() == 2
    assert ContainerOpening.objects.count() == 2


# ---------------------------------------------------------------------------
# opening_view_model
# ---------------------------------------------------------------------------


def test_opening_view_model_merged_in_slot_order(club, character, club_admin):
    rope = Item.objects.create(club=club, name="Rope", value_cp=1)
    torch = Item.objects.create(club=club, name="Torch", value_cp=1)
    container = make_container(club, name="Box")
    add_slot(container, [(rope, 1, 1, 1)], position=0)
    add_slot(container, [(torch, 2, 2, 1)], position=1)
    add_slot(container, [(rope, 3, 3, 1)], position=2)
    record(character, "award", [Line(item=container, quantity=1)], actor=club_admin)
    opening = open_container(character, container, club_admin, rng=random.Random(1))

    rows = opening_view_model(opening)
    assert rows == [
        {"item": rope, "qty": 4},
        {"item": torch, "qty": 2},
    ]
