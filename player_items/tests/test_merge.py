"""Tests for the merge/match views and service (U162).

Covers:
- Merge several review groups into one new catalogue item
- Match several review groups to an existing catalogue item via item picker
- Holder who already has the matched item gets quantities added in one ledger entry
- Holder with multiple merged entries gets exactly one ledger entry
- Similar-name suggestions shown but never auto-picked
- Preview shows each holder's before/after quantities
- All-or-nothing transaction: failure rolls back everything
"""

import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import item_quantities
from player_characters.models import Character
from player_items.models import PlayerItem, PlayerItemChange, PlayerNotice
from player_items.resolve import Target, resolve, suggest_matches

pytestmark = [pytest.mark.story("U162"), pytest.mark.django_db]


# --- helpers -------------------------------------------------------------


def merge_form_url(club):
    return reverse("player_items:merge_form", args=[club.slug])


def merge_confirm_url(club):
    return reverse("player_items:merge_confirm", args=[club.slug])


def review_url(club):
    return reverse("player_items:review", args=[club.slug])


def suggest_url(club):
    return reverse("player_items:suggest", args=[club.slug])


def make_item(club, character, name="Potion", quantity=1, review="open"):
    return PlayerItem.objects.create(
        club=club, character=character, name=name, quantity=quantity, review=review
    )


@pytest.fixture
def other_character(club, other_player):
    owner = club.memberships.get(user=other_player)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.fixture
def existing_item(club):
    return Item.objects.create(club=club, name="Healing Potion", value_cp=50)


@pytest.fixture
def existing_item2(club):
    return Item.objects.create(club=club, name="Rope", value_cp=100)


# --- service: merge into new item ----------------------------------------


def test_merge_several_groups_into_new_item(club, club_admin, character, other_character):
    """Merge multiple name_key groups into one new catalogue item."""
    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)  # same name_key
    make_item(club, other_character, "Health Potion", 4)  # different name_key
    make_item(club, other_character, "Elixir", 1)  # another name_key

    entries = PlayerItem.objects.for_club(club).filter(
        name_key__in=["potion", "health potion", "elixir"]
    )
    resolve(club, entries, Target(name="Healing Potion"), club_admin, mode="merge")

    # New item created
    new_item = Item.objects.for_club(club).get(name="Healing Potion")
    assert not new_item.is_stacked

    # All entries resolved
    assert PlayerItem.objects.for_club(club).filter(review="open").count() == 0
    assert PlayerItem.objects.for_club(club).filter(review="resolved").count() == 4

    # One ledger entry per holder
    promoted = LedgerEntry.objects.for_club(club).filter(
        kind="adjustment", note="player-written item merged"
    )
    assert promoted.count() == 2  # character + other_character

    char_entry = promoted.get(character=character)
    assert char_entry.lines.get().quantity == 5  # 2 + 3
    assert char_entry.lines.get().coins == 0

    other_entry = promoted.get(character=other_character)
    assert other_entry.lines.get().quantity == 5  # 4 + 1
    assert other_entry.lines.get().coins == 0

    # History rows keep old names, kind MERGED
    changes = PlayerItemChange.objects.for_club(club).filter(kind="merged")
    assert changes.count() == 4
    expected_names = {"Potion", "potion", "Health Potion", "Elixir"}
    assert set(changes.values_list("old_name", flat=True)) == expected_names
    assert all(c.new_name == "Healing Potion" for c in changes)

    # One notice per holder, kind ITEM_MERGED
    notices = PlayerNotice.objects.for_club(club).filter(kind="item_merged")
    assert notices.count() == 2
    for notice in notices:
        assert "merged" in notice.text.lower()
        assert "Healing Potion" in notice.text


def test_merge_stacked_with_factor(club, club_admin, character):
    """Merge with stacked target and quantity factor."""
    make_item(club, character, "Arrow", 10)
    make_item(club, character, "arrow", 5)

    entries = PlayerItem.objects.for_club(club).filter(name_key="arrow")
    target = Target(name="Arrow Bundle", is_stacked=True, unit_name="arrow", quantity_factor=10)
    resolve(club, entries, target, club_admin, mode="merge")

    new_item = Item.objects.for_club(club).get(name="Arrow Bundle")
    assert new_item.is_stacked
    assert new_item.unit_name == "arrow"

    line = LedgerEntry.objects.for_club(club).get(character=character).lines.get()
    assert line.quantity == 150  # (10 + 5) * 10


# --- service: match to existing item -------------------------------------


def test_match_several_groups_to_existing_item(
    club, club_admin, character, other_character, existing_item
):
    """Match multiple name_key groups to an existing catalogue item."""
    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)
    make_item(club, other_character, "Health Potion", 4)

    entries = PlayerItem.objects.for_club(club).filter(name_key__in=["potion", "health potion"])
    resolve(club, entries, Target(item=existing_item), club_admin, mode="match")

    # No new item created
    assert Item.objects.for_club(club).count() == 1

    # All entries resolved
    assert PlayerItem.objects.for_club(club).filter(review="open").count() == 0

    # One ledger entry per holder, kind adjustment, note says "matched"
    matched = LedgerEntry.objects.for_club(club).filter(
        kind="adjustment", note="player-written item matched"
    )
    assert matched.count() == 2

    char_entry = matched.get(character=character)
    assert char_entry.lines.get().quantity == 5  # 2 + 3
    assert char_entry.lines.get().item == existing_item

    other_entry = matched.get(character=other_character)
    assert other_entry.lines.get().quantity == 4
    assert other_entry.lines.get().item == existing_item

    # History rows kind MATCHED
    changes = PlayerItemChange.objects.for_club(club).filter(kind="matched")
    assert changes.count() == 3
    assert all(c.new_name == "Healing Potion" for c in changes)
    assert all(c.item == existing_item for c in changes)

    # Notices kind ITEM_MATCHED
    notices = PlayerNotice.objects.for_club(club).filter(kind="item_matched")
    assert notices.count() == 2
    for notice in notices:
        assert "matched" in notice.text.lower()
        assert "Healing Potion" in notice.text


def test_match_holder_already_has_item_adds_quantities(club, club_admin, character, existing_item):
    """Holder who already has the matched item gets quantities added in one ledger entry."""
    # Character already has 3 Healing Potions in ledger
    from ledger.services import Line, record

    record(character, "award", [Line(item=existing_item, quantity=3, coins=0)])
    assert item_quantities(character)[existing_item.pk] == 3

    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)

    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(item=existing_item), club_admin, mode="match")

    # One ledger entry (adjustment) that adds 5 to existing 3
    matched = LedgerEntry.objects.for_club(club).filter(
        kind="adjustment", note="player-written item matched"
    )
    assert matched.count() == 1
    line = matched.get(character=character).lines.get()
    assert line.quantity == 5  # only the new quantity
    assert line.item == existing_item

    # Total should now be 8
    assert item_quantities(character)[existing_item.pk] == 8

    # History rows kind MATCHED
    changes = PlayerItemChange.objects.for_club(club).filter(kind="matched")
    assert changes.count() == 2


def test_holder_with_multiple_merged_entries_gets_one_ledger_entry(club, club_admin, character):
    """Holder with two merged entries gets exactly one ledger entry."""
    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)
    make_item(club, character, "Health Potion", 4)

    entries = PlayerItem.objects.for_club(club).filter(name_key__in=["potion", "health potion"])
    resolve(club, entries, Target(name="Healing Potion"), club_admin, mode="merge")

    # Only ONE ledger entry for this character
    merged = LedgerEntry.objects.for_club(club).filter(
        kind="adjustment", note="player-written item merged"
    )
    assert merged.count() == 1
    line = merged.get(character=character).lines.get()
    assert line.quantity == 9  # 2 + 3 + 4


# --- suggestions ----------------------------------------------------------


def test_suggestions_never_auto_pick(club, existing_item, existing_item2):
    """suggest_matches returns a list, never chooses automatically."""
    matches = suggest_matches(club, "Healing Potoin")
    assert isinstance(matches, list)
    assert "Healing Potion" in matches
    assert "Rope" not in matches  # low similarity

    # Empty list when no matches
    matches = suggest_matches(club, "Completely Different")
    assert matches == []

    # Up to 5 matches
    for i in range(7):
        Item.objects.create(club=club, name=f"Item {i}")
    matches = suggest_matches(club, "Item")
    assert len(matches) <= 5


# --- preview (service level) ---------------------------------------------


def test_preview_data_merge(club, club_admin, character, other_character):
    """Preview shows before/after for merge mode."""
    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)
    make_item(club, other_character, "Health Potion", 4)

    from player_items.forms import MergeForm
    from player_items.views.merge import _build_holders, _build_preview_data

    name_keys = ["potion", "health potion"]
    entries = list(PlayerItem.objects.for_club(club).filter(name_key__in=name_keys))
    _build_holders(entries)

    form = MergeForm(
        {
            "name_keys": ["potion", "health potion"],
            "mode": "merge",
            "name": "Healing Potion",
            "quantity_factor": "1",
        },
        club=club,
    )
    assert form.is_valid()

    preview = _build_preview_data(entries, form, club)

    assert len(preview["holders"]) == 2
    char_holder = next(h for h in preview["holders"] if h["character"] == character)
    other_holder = next(h for h in preview["holders"] if h["character"] == other_character)

    assert char_holder["total_quantity"] == 5
    assert char_holder["new_total_quantity"] == 5
    assert char_holder["existing_quantity"] == 0

    assert other_holder["total_quantity"] == 4
    assert other_holder["new_total_quantity"] == 4


def test_preview_data_match_shows_existing_quantity(club, club_admin, character, existing_item):
    """Preview shows existing quantity for match mode."""
    # Character already has 3 of the item
    from ledger.services import Line, record

    record(character, "award", [Line(item=existing_item, quantity=3, coins=0)])

    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)

    from player_items.forms import MergeForm
    from player_items.views.merge import _build_holders, _build_preview_data

    entries = list(PlayerItem.objects.for_club(club).filter(name_key="potion"))
    _build_holders(entries)

    form = MergeForm(
        {
            "name_keys": ["potion"],
            "mode": "match",
            "item": existing_item.pk,
            "quantity_factor": "1",
        },
        club=club,
    )
    assert form.is_valid()

    preview = _build_preview_data(entries, form, club)

    assert len(preview["holders"]) == 1
    char_holder = preview["holders"][0]
    assert char_holder["total_quantity"] == 5
    assert char_holder["existing_quantity"] == 3
    assert char_holder["new_total_quantity"] == 8


# --- all-or-nothing ------------------------------------------------------


def test_all_or_nothing_rolls_back_on_failure(club, club_admin, character):
    """All-or-nothing transaction: failure rolls back everything."""
    from unittest.mock import patch

    make_item(club, character, "Potion", 2)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")

    with patch("player_items.resolve.record_many", side_effect=ValueError("boom")):
        with pytest.raises(ValueError):
            resolve(club, entries, Target(name="Potion"), club_admin, mode="merge")

    # Item was created then rolled back; nothing persists.
    assert Item.objects.for_club(club).filter(name="Potion").count() == 0
    assert PlayerItemChange.objects.for_club(club).count() == 0
    assert PlayerNotice.objects.for_club(club).count() == 0
    assert LedgerEntry.objects.for_club(club).count() == 0
    # Entries remain open
    assert PlayerItem.objects.for_club(club).filter(name_key="potion", review="open").count() == 1


def test_match_all_or_nothing_rolls_back(club, club_admin, character, existing_item):
    """Match mode also rolls back on failure."""
    from unittest.mock import patch

    make_item(club, character, "Potion", 2)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")

    with patch("player_items.resolve.record_many", side_effect=ValueError("boom")):
        with pytest.raises(ValueError):
            resolve(club, entries, Target(item=existing_item), club_admin, mode="match")

    assert PlayerItemChange.objects.for_club(club).count() == 0
    assert PlayerNotice.objects.for_club(club).count() == 0
    assert LedgerEntry.objects.for_club(club).count() == 0
    assert PlayerItem.objects.for_club(club).filter(name_key="potion", review="open").count() == 1


# --- views: merge form ----------------------------------------------------


def test_club_admin_get_merge_form(club, login, club_admin, character, other_character):
    """Club admin can GET the merge form with multiple groups."""
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Health Potion", 3)

    c = login(club_admin)
    url = f"{merge_form_url(club)}?name_keys=potion&name_keys=health+potion"
    r = c.get(url, HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Merge player-written items" in body
    assert "Make one new item" in body
    assert "Match to existing item" in body
    assert "Potion" in body
    assert "Health Potion" in body


def test_player_cannot_access_merge(club, login, player, character):
    """Non-admin cannot access merge form."""
    make_item(club, character, "Potion", 2)
    c = login(player)
    url = f"{merge_form_url(club)}?name_keys=potion"
    assert c.get(url, HTTP_HX_REQUEST="true").status_code == 403


def test_merge_form_requires_at_least_two_groups(club, login, club_admin, character):
    """Merge form redirects if fewer than 2 groups selected."""
    make_item(club, character, "Potion", 2)
    c = login(club_admin)
    url = f"{merge_form_url(club)}?name_keys=potion"
    r = c.get(url, HTTP_HX_REQUEST="true")
    assert r.status_code == 302
    assert r["Location"] == review_url(club)


def test_merge_form_post_valid_redirects_to_preview(
    club, login, club_admin, character, other_character
):
    """Valid POST to merge form shows preview."""
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Health Potion", 3)

    c = login(club_admin)
    r = c.post(
        merge_form_url(club),
        {
            "name_keys": ["potion", "health potion"],
            "mode": "merge",
            "name": "Healing Potion",
            "quantity_factor": "1",
        },
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert "Preview merge" in body
    assert "Healing Potion" in body
    assert "Aria" in body
    assert "Borin" in body


def test_merge_form_post_match_shows_item_picker(
    club, login, club_admin, character, other_character, existing_item
):
    """Match mode shows item picker in preview."""
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Health Potion", 3)

    c = login(club_admin)
    r = c.post(
        merge_form_url(club),
        {
            "name_keys": ["potion", "health potion"],
            "mode": "match",
            "item": existing_item.pk,
            "quantity_factor": "1",
        },
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert "Preview merge" in body
    assert "Healing Potion" in body


def test_merge_form_post_invalid_re_renders_with_error(
    club, login, club_admin, character, other_character
):
    """Invalid form (e.g., missing name) re-renders with error."""
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Health Potion", 3)

    c = login(club_admin)
    r = c.post(
        merge_form_url(club),
        {
            "name_keys": ["potion", "health potion"],
            "mode": "merge",
            "name": "",  # missing
            "quantity_factor": "1",
        },
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert "required" in body.lower() or "error" in body.lower()


def test_merge_confirm_executes_and_redirects(club, login, club_admin, character, other_character):
    """Confirm POST executes the merge and redirects to review."""
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Health Potion", 3)

    c = login(club_admin)
    # First, POST to form to set up session
    c.post(
        merge_form_url(club),
        {
            "name_keys": ["potion", "health potion"],
            "mode": "merge",
            "name": "Healing Potion",
            "quantity_factor": "1",
        },
        HTTP_HX_REQUEST="true",
    )
    # Then confirm
    r = c.post(merge_confirm_url(club), HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r["HX-Redirect"] == review_url(club)

    # Check result
    Item.objects.for_club(club).get(name="Healing Potion")
    assert PlayerItem.objects.for_club(club).filter(review="resolved").count() == 2


def test_merge_confirm_match_executes_and_redirects(
    club, login, club_admin, character, other_character, existing_item
):
    """Confirm POST executes the match and redirects to review."""
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Health Potion", 3)

    c = login(club_admin)
    c.post(
        merge_form_url(club),
        {
            "name_keys": ["potion", "health potion"],
            "mode": "match",
            "item": existing_item.pk,
            "quantity_factor": "1",
        },
        HTTP_HX_REQUEST="true",
    )
    r = c.post(merge_confirm_url(club), HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r["HX-Redirect"] == review_url(club)

    assert PlayerItem.objects.for_club(club).filter(review="resolved").count() == 2
    assert Item.objects.for_club(club).count() == 1  # no new item


# --- suggestions endpoint -------------------------------------------------


def test_suggest_endpoint_returns_suggestions(club, login, club_admin, existing_item):
    """HTMX suggest endpoint returns matching item names."""
    c = login(club_admin)
    r = c.get(f"{suggest_url(club)}?name=Healing+Potoin", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Healing Potion" in body


def test_suggest_endpoint_empty_for_short_query(club, login, club_admin):
    """Suggest endpoint returns empty for queries < 2 chars."""
    c = login(club_admin)
    r = c.get(f"{suggest_url(club)}?name=H", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert body.strip() == ""


# --- review page: merge button -------------------------------------------


def test_review_page_has_checkboxes_and_merge_button(
    club, login, club_admin, character, other_character
):
    """Review page shows checkboxes and merge button."""
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Rope", 1)

    c = login(club_admin)
    body = c.get(review_url(club)).content.decode()
    assert 'name="name_keys"' in body
    assert 'id="select-all"' in body
    assert 'id="merge-selected-btn"' in body
    assert "Merge selected" in body


def test_merge_button_disabled_until_two_checked(
    club, login, club_admin, character, other_character
):
    """Merge button is disabled until at least 2 checkboxes checked."""
    make_item(club, character, "Potion", 2)
    make_item(club, other_character, "Rope", 1)

    c = login(club_admin)
    body = c.get(review_url(club)).content.decode()
    # Button should have disabled attribute initially
    assert "disabled" in body
