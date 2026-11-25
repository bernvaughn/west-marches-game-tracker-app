"""Tests for downtime expected value computation (U157, U158)."""

import pytest
from django.urls import reverse

from downtime.ev import (
    entry_value_cp,
    expected_value,
    expected_value_cp,
    item_value_cp,
)
from downtime.models import DowntimeAction, DowntimeEntry, DowntimeEntryItem

pytestmark = [pytest.mark.django_db]


def url(name, club, *args):
    return reverse(f"downtime:{name}", args=[club.slug, *args])


# ---- item_value_cp ----


def test_item_value_cp_plain(item):
    """Plain item value is value_cp * quantity."""
    item.value_cp = 1500  # 15 gp
    item.is_stacked = False
    item.save()
    assert item_value_cp(item, 1) == 1500
    assert item_value_cp(item, 3) == 4500


def test_item_value_cp_stacked(item):
    """Stacked item uses value_cp * quantity // value_units."""
    item.value_cp = 5000  # 50 gp for 50 units
    item.value_units = 50
    item.is_stacked = True
    item.unit_name = "ft"
    item.save()
    # 5000 * 10 // 50 = 1000 cp = 10 gp per 10 ft
    assert item_value_cp(item, 10) == 1000
    # 5000 * 50 // 50 = 5000 cp = 50 gp per 50 ft
    assert item_value_cp(item, 50) == 5000


def test_item_value_cp_zero_value(item):
    """Zero value returns 0."""
    item.value_cp = 0
    item.save()
    assert item_value_cp(item, 1) == 0


def test_item_value_cp_none_item():
    """None item returns 0."""
    assert item_value_cp(None, 1) == 0


# ---- entry_value_cp ----


def test_entry_value_cp_only_coins(entry):
    """Entry with only coins returns coins value."""
    entry.coins = 2500  # 25 gp
    entry.save()
    assert entry_value_cp(entry) == 2500


def test_entry_value_cp_only_items(entry, item):
    """Entry with only items returns sum of item values."""
    entry.coins = 0
    entry.save()
    item.value_cp = 1000  # 10 gp
    item.is_stacked = False
    item.save()
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=2)
    assert entry_value_cp(entry) == 2000


def test_entry_value_cp_coins_and_items(entry, item):
    """Entry with coins and items sums both."""
    entry.coins = 1000  # 10 gp
    entry.save()
    item.value_cp = 500  # 5 gp
    item.is_stacked = False
    item.save()
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=3)
    assert entry_value_cp(entry) == 1000 + 1500


def test_entry_value_cp_stacked_items(entry, item):
    """Entry with stacked items computes correctly."""
    entry.coins = 0
    entry.save()
    item.value_cp = 10000  # 100 gp for 100 units
    item.value_units = 100
    item.is_stacked = True
    item.unit_name = "arrow"
    item.save()
    # 10000 * 50 // 100 = 5000 cp = 50 gp for 50 arrows
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=50)
    assert entry_value_cp(entry) == 5000


def test_entry_value_cp_no_items_or_coins(entry):
    """Entry with nothing returns 0."""
    entry.coins = 0
    entry.save()
    assert entry_value_cp(entry) == 0


# ---- expected_value_cp ----


def test_expected_value_cp_weighted_table(action):
    """Expected value of a weighted table is correct."""
    e1 = DowntimeEntry.objects.create(
        action=action, label="High", weight=3, coins=3000, order=0
    )  # 30 gp
    e2 = DowntimeEntry.objects.create(
        action=action, label="Low", weight=1, coins=1000, order=1
    )  # 10 gp
    # (3*3000 + 1*1000) / 4 = 10000/4 = 2500 cp = 25 gp
    entries = [e1, e2]
    assert expected_value_cp(entries) == 2500


def test_expected_value_cp_zero_weight_returns_zero():
    """Zero total weight returns 0 (empty list)."""
    assert expected_value_cp([]) == 0


def test_expected_value_cp_zero_value_entries_count_as_zero(action):
    """Entries with no value count as zero in weighted sum."""
    e1 = DowntimeEntry.objects.create(
        action=action, label="Value", weight=2, coins=2000, order=0
    )  # 20 gp
    e2 = DowntimeEntry.objects.create(
        action=action, label="Nothing", weight=2, coins=0, order=1
    )  # 0 gp
    # (2*2000 + 2*0) / 4 = 4000/4 = 1000 cp = 10 gp
    assert expected_value_cp([e1, e2]) == 1000


def test_expected_value_cp_empty_list():
    """Empty entries list returns 0."""
    assert expected_value_cp([]) == 0


def test_expected_value_cp_with_items(action, item):
    """Expected value works with item values."""
    item.value_cp = 1000  # 10 gp
    item.is_stacked = False
    item.save()
    e1 = DowntimeEntry.objects.create(action=action, label="Item", weight=1, coins=0, order=0)
    DowntimeEntryItem.objects.create(entry=e1, item=item, quantity=1)
    e2 = DowntimeEntry.objects.create(
        action=action, label="Coins", weight=1, coins=2000, order=1
    )  # 20 gp
    # (1*1000 + 1*2000) / 2 = 1500 cp = 15 gp
    assert expected_value_cp([e1, e2]) == 1500


def test_expected_value_cp_with_stacked_items(action, item):
    """Expected value works with stacked items."""
    item.value_cp = 10000  # 100 gp for 100 units
    item.value_units = 100
    item.is_stacked = True
    item.unit_name = "ft"
    item.save()
    e1 = DowntimeEntry.objects.create(action=action, label="Rope", weight=1, coins=0, order=0)
    # 10000 * 50 // 100 = 5000 cp = 50 gp for 50 ft
    DowntimeEntryItem.objects.create(entry=e1, item=item, quantity=50)
    e2 = DowntimeEntry.objects.create(action=action, label="Coins", weight=1, coins=0, order=1)
    # (1*5000 + 1*0) / 2 = 2500 cp = 25 gp
    assert expected_value_cp([e1, e2]) == 2500


# ---- expected_value (formatted) ----


def test_expected_value_formatted(action):
    """Formatted expected value uses format_coins."""
    e1 = DowntimeEntry.objects.create(
        action=action, label="A", weight=1, coins=1500, order=0
    )  # 15 gp
    e2 = DowntimeEntry.objects.create(
        action=action, label="B", weight=1, coins=500, order=1
    )  # 5 gp
    # (1500 + 500) / 2 = 1000 cp = 10 gp
    assert expected_value([e1, e2]) == "10 gp"


def test_expected_value_zero_returns_empty_string(action):
    """Zero expected value returns empty string."""
    e1 = DowntimeEntry.objects.create(action=action, label="A", weight=1, coins=0, order=0)
    assert expected_value([e1]) == ""


# ---- entry_value_text ----


def test_entry_value_text_only_coins(entry):
    """Entry value text shows coins."""
    entry.coins = 1500
    entry.save()
    from downtime.ev import entry_value_text

    assert entry_value_text(entry) == "15 gp"


def test_entry_value_text_only_items(entry, item):
    """Entry value text shows item values."""
    entry.coins = 0
    entry.save()
    item.value_cp = 1000
    item.is_stacked = False
    item.save()
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=2)
    from downtime.ev import entry_value_text

    assert entry_value_text(entry) == "2 x 10 gp"


def test_entry_value_text_stacked_item(entry, item):
    """Entry value text shows stacked item value per unit."""
    entry.coins = 0
    entry.save()
    item.value_cp = 5000  # 50 gp for 50 units
    item.value_units = 50
    item.is_stacked = True
    item.unit_name = "ft"
    item.save()
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=10)
    from downtime.ev import entry_value_text

    # 5000 // 50 = 100 cp = 1 gp per ft
    assert entry_value_text(entry) == "10 x 1 gp per ft"


def test_entry_value_text_coins_and_items(entry, item):
    """Entry value text combines coins and items."""
    entry.coins = 1000
    entry.save()
    item.value_cp = 500
    item.is_stacked = False
    item.save()
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=1)
    from downtime.ev import entry_value_text

    assert entry_value_text(entry) == "10 gp, 5 gp"


def test_entry_value_text_none(entry):
    """Entry with no value returns empty string."""
    entry.coins = 0
    entry.save()
    from downtime.ev import entry_value_text

    assert entry_value_text(entry) == ""


# ---- template filter expected_value_total ----


def test_expected_value_total_filter(login, club, club_admin, action, item):
    """Template filter returns formatted expected value on the manage page."""
    # Create entries with items
    item.value_cp = 1000  # 10 gp
    item.is_stacked = False
    item.save()
    e1 = DowntimeEntry.objects.create(
        action=action, label="A", weight=2, coins=2000, order=0
    )  # 20 gp
    DowntimeEntryItem.objects.create(entry=e1, item=item, quantity=1)  # +10 gp = 30 gp total
    DowntimeEntry.objects.create(action=action, label="B", weight=2, coins=0, order=1)
    # (2*3000 + 2*0) / 4 = 1500 cp = 15 gp

    c = login(club_admin)
    r = c.get(url("action_edit", club, action.pk))
    body = r.content.decode()
    assert "Expected value: 15 gp" in body


def test_expected_value_total_filter_not_shown_when_zero(login, club, club_admin, action):
    """Expected value not shown when zero."""
    DowntimeEntry.objects.create(action=action, label="A", weight=1, coins=0, order=0)
    c = login(club_admin)
    r = c.get(url("action_edit", club, action.pk))
    body = r.content.decode()
    assert "Expected value:" not in body


# ---- item value shown per entry ----


def test_item_value_shown_per_entry_row(login, club, club_admin, action, item):
    """Each entry row shows its item's value."""
    item.value_cp = 2500  # 25 gp
    item.is_stacked = False
    item.save()
    e1 = DowntimeEntry.objects.create(action=action, label="A", weight=1, coins=0, order=0)
    DowntimeEntryItem.objects.create(entry=e1, item=item, quantity=1)

    c = login(club_admin)
    r = c.get(url("action_edit", club, action.pk))
    body = r.content.decode()
    assert "Value: 25 gp" in body


def test_stacked_item_value_shown_per_entry_row(login, club, club_admin, action, item):
    """Stacked item shows value per unit."""
    item.value_cp = 10000  # 100 gp for 100 units
    item.value_units = 100
    item.is_stacked = True
    item.unit_name = "arrow"
    item.save()
    e1 = DowntimeEntry.objects.create(action=action, label="A", weight=1, coins=0, order=0)
    DowntimeEntryItem.objects.create(entry=e1, item=item, quantity=50)

    c = login(club_admin)
    r = c.get(url("action_edit", club, action.pk))
    body = r.content.decode()
    # 10000 // 100 = 100 cp = 1 gp per arrow
    assert "Value: 1 gp per arrow" in body


# ---- saved data identical ----


def test_post_create_round_trip_saves_identical_data(login, club, club_admin, item):
    """POST create round trip saves identical data."""
    item.value_cp = 1000
    item.is_stacked = False
    item.save()

    data = {
        "name": "Fishing",
        "description": "Cast a line.",
        "cost": "2",
        "start_date": "",
        "end_date": "",
        "entries-TOTAL_FORMS": "1",
        "entries-INITIAL_FORMS": "0",
        "entries-MIN_NUM_FORMS": "0",
        "entries-MAX_NUM_FORMS": "1000",
        "entries-0-label": "Trout",
        "entries-0-weight": "3",
        "entries-0-order": "0",
        "entries-0-coins_pp": "",
        "entries-0-coins_gp": "1",
        "entries-0-coins_sp": "",
        "entries-0-coins_cp": "",
        "entries-0-items-TOTAL_FORMS": "1",
        "entries-0-items-INITIAL_FORMS": "0",
        "entries-0-items-MIN_NUM_FORMS": "0",
        "entries-0-items-MAX_NUM_FORMS": "1000",
        "entries-0-items-0-item": str(item.pk),
        "entries-0-items-0-quantity": "1",
    }

    c = login(club_admin)
    r = c.post(url("action_new", club), data)
    assert r.status_code == 302

    action = DowntimeAction.objects.get(name="Fishing")
    entry = action.entries.get()
    assert entry.weight == 3
    assert entry.coins == 100
    assert entry.items.get().item == item
    assert entry.items.get().quantity == 1


def test_post_edit_round_trip_saves_identical_data(login, club, club_admin, action, entry, item):
    """POST edit round trip saves identical data."""
    item.value_cp = 1000
    item.is_stacked = False
    item.save()

    # Add item to existing entry
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=2)

    data = {
        "name": action.name,
        "description": action.description,
        "cost": str(action.cost),
        "start_date": action.start_date.strftime("%Y-%m-%d") if action.start_date else "",
        "end_date": action.end_date.strftime("%Y-%m-%d") if action.end_date else "",
        "entries-TOTAL_FORMS": "1",
        "entries-INITIAL_FORMS": "1",
        "entries-MIN_NUM_FORMS": "0",
        "entries-MAX_NUM_FORMS": "1000",
        "entries-0-id": str(entry.pk),
        "entries-0-label": "Updated Label",
        "entries-0-weight": str(entry.weight),
        "entries-0-order": "0",
        "entries-0-coins_pp": "",
        "entries-0-coins_gp": "2",
        "entries-0-coins_sp": "",
        "entries-0-coins_cp": "",
        "entries-0-items-TOTAL_FORMS": "1",
        "entries-0-items-INITIAL_FORMS": "1",
        "entries-0-items-MIN_NUM_FORMS": "0",
        "entries-0-items-MAX_NUM_FORMS": "1000",
        "entries-0-items-0-id": str(entry.items.first().pk),
        "entries-0-items-0-item": str(item.pk),
        "entries-0-items-0-quantity": "3",
    }

    c = login(club_admin)
    r = c.post(url("action_edit", club, action.pk), data)
    assert r.status_code == 302

    entry.refresh_from_db()
    assert entry.label == "Updated Label"
    assert entry.coins == 200
    assert entry.items.get().quantity == 3
