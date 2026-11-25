"""Tests for the promote service function (U161).

Covers one ledger entry per holder with the right quantity, coins unchanged,
entries marked resolved, history rows keeping old names, one notice per
holder, refusal of an existing name with suggestions, stacked targets, and
all-or-nothing rollback.
"""

from unittest.mock import patch

import pytest

from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import Line, coin_balance, record
from player_characters.models import Character
from player_items.models import PlayerItem, PlayerItemChange, PlayerNotice
from player_items.resolve import ResolveError, Target, resolve, suggest_matches

pytestmark = [pytest.mark.story("U161"), pytest.mark.django_db]


# --- helpers -------------------------------------------------------------


@pytest.fixture
def other_character(club, other_player):
    owner = club.memberships.get(user=other_player)
    return Character.objects.create(club=club, owner=owner, name="Borin")


def make_item(club, character, name="Potion", quantity=1, review="open"):
    return PlayerItem.objects.create(
        club=club, character=character, name=name, quantity=quantity, review=review
    )


# --- service: happy path -------------------------------------------------


def test_one_ledger_entry_per_holder_with_right_quantity(
    club, character, other_character, club_admin
):
    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)  # same holder, same group
    make_item(club, other_character, "Potion", 4)

    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(name="Healing Potion"), club_admin)

    promoted = LedgerEntry.objects.for_club(club).filter(
        kind="adjustment", note="player-written item promoted"
    )
    assert promoted.count() == 2  # one per holder

    char_entry = promoted.get(character=character)
    assert char_entry.lines.get().quantity == 5  # 2 + 3
    assert char_entry.lines.get().coins == 0

    other_entry = promoted.get(character=other_character)
    assert other_entry.lines.get().quantity == 4


def test_coins_unchanged(club, character, club_admin):
    make_item(club, character, "Potion", 2)
    record(character, "award", [Line(item=None, quantity=0, coins=100)])
    assert coin_balance(character) == 100

    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(name="Potion"), club_admin)
    assert coin_balance(character) == 100  # adjustment line has coins=0


def test_entries_marked_resolved(club, character, club_admin):
    make_item(club, character, "Potion", 2)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(name="Potion"), club_admin)

    item = PlayerItem.objects.for_club(club).get(name="Potion")
    assert item.review == "resolved"
    assert item.resolved_by_change is not None
    assert item.resolved_by_change.kind == PlayerItemChange.Kind.PROMOTED


def test_history_rows_keep_old_names(club, character, club_admin):
    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(name="Healing Potion"), club_admin)

    changes = PlayerItemChange.objects.for_club(club).filter(character=character, kind="promoted")
    assert changes.count() == 2
    assert set(changes.values_list("old_name", flat=True)) == {"Potion", "potion"}
    for change in changes:
        assert change.new_name == "Healing Potion"
        assert change.item_id is not None
        assert change.by_id == club_admin.id


def test_one_notice_per_holder(club, character, other_character, club_admin):
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Potion", 4)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(name="Healing Potion"), club_admin)

    notices = PlayerNotice.objects.for_club(club).filter(kind="item_promoted")
    assert notices.count() == 2  # one per holder
    assert set(notices.values_list("membership", flat=True)) == {
        character.owner_id,
        other_character.owner_id,
    }
    for notice in notices:
        assert notice.character is not None
        assert "Potion" in notice.text
        assert "Healing Potion" in notice.text


# --- refusal: existing name ---------------------------------------------


def test_refuses_existing_item_name(club, character, club_admin, item):
    # ``item`` fixture: an Item named "Rope" in this club.
    make_item(club, character, "Rope", 1)
    entries = PlayerItem.objects.for_club(club).filter(name_key="rope")
    target = Target(name="Rope")

    with pytest.raises(ResolveError) as exc:
        resolve(club, entries, target, club_admin)
    assert "Rope" in str(exc.value)

    # All-or-nothing: nothing written.
    assert Item.objects.for_club(club).filter(name="Rope").count() == 1  # only the pre-existing one
    assert PlayerItemChange.objects.for_club(club).count() == 0
    assert PlayerNotice.objects.for_club(club).count() == 0
    assert LedgerEntry.objects.for_club(club).count() == 0


def test_suggests_matches(club, club_admin):
    Item.objects.create(club=club, name="Healing Potion")
    Item.objects.create(club=club, name="Healing Salve")
    Item.objects.create(club=club, name="Rope")

    matches = suggest_matches(club, "Healing Potoin")
    assert "Healing Potion" in matches
    # Never chooses: returns a list of suggestions, never a single pick.
    assert isinstance(matches, list)


# --- stacked target -------------------------------------------------------


def test_stacked_target_uses_units_and_factor(club, character, club_admin):
    make_item(club, character, "Arrow", 10)
    entries = PlayerItem.objects.for_club(club).filter(name_key="arrow")
    target = Target(name="Arrow Bundle", is_stacked=True, unit_name="arrow", quantity_factor=10)
    resolve(club, entries, target, club_admin)

    new_item = Item.objects.for_club(club).get(name="Arrow Bundle")
    assert new_item.is_stacked
    assert new_item.unit_name == "arrow"

    line = LedgerEntry.objects.for_club(club).get(character=character).lines.get()
    assert line.quantity == 100  # 10 x factor 10
    assert line.item_id == new_item.id


# --- existing target ------------------------------------------------------


def test_existing_target_must_be_same_club(club, character, other_club, club_admin):
    foreign_item = Item.objects.create(club=other_club, name="Foreign")
    make_item(club, character, "Potion", 2)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    target = Target(item=foreign_item)

    with pytest.raises(ResolveError):
        resolve(club, entries, target, club_admin)

    assert PlayerItemChange.objects.for_club(club).count() == 0


# --- all-or-nothing -------------------------------------------------------


def test_all_or_nothing_rolls_back_on_failure(club, character, club_admin):
    make_item(club, character, "Potion", 2)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    target = Target(name="Potion")

    with patch("player_items.resolve.record_many", side_effect=ValueError("boom")):
        with pytest.raises(ValueError):
            resolve(club, entries, target, club_admin)

    # Item was created then rolled back; nothing persists.
    assert Item.objects.for_club(club).filter(name="Potion").count() == 0
    assert PlayerItemChange.objects.for_club(club).count() == 0
    assert PlayerNotice.objects.for_club(club).count() == 0
    assert LedgerEntry.objects.for_club(club).count() == 0
    # Entries remain open, not marked resolved.
    assert PlayerItem.objects.for_club(club).filter(name_key="potion", review="open").count() == 1
