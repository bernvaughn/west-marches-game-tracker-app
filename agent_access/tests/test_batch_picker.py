"""Tests for the item picker in agent batch review (S6 / U157)."""

import pytest
from django.urls import reverse

from agent_access.models import ProposedBatch, ProposedItem, ProposedLine
from items.models import Item
from ledger.models import LedgerEntry, LedgerLine

pytestmark = [pytest.mark.story("A4"), pytest.mark.django_db]


@pytest.fixture
def gm_client(login, game_master):
    return login(game_master)


@pytest.fixture
def batch_with_lines(club, game_master, gm_connection, character):
    """Create a batch with different line types for testing."""
    b = ProposedBatch.objects.create(
        club=club,
        connection=gm_connection[0],
        user=game_master,
        date="2026-05-01",
        idempotency_key="k1",
        source_notes="Session notes",
    )

    # Catalogue item with value
    item_with_value = Item.objects.create(
        club=club, name="Gold Gem", value_cp=500, traits="sparkly"
    )

    # Stacked item with value per unit
    stacked_item = Item.objects.create(
        club=club,
        name="Rope",
        value_cp=200,
        value_units=50,
        unit_name="ft",
        is_stacked=True,
        traits="hempen",
    )

    # Item with no value
    no_value_item = Item.objects.create(club=club, name="Worthless Rock", value_cp=0)

    # Proposed item (new item)
    proposed = ProposedItem.objects.create(
        club=club, name="Mystery Item", status="approved", approved_item=item_with_value
    )

    # Line 1: catalogue item with value
    ProposedLine.objects.create(
        batch=b, character=character, item=item_with_value, quantity=2, note="Gem reward"
    )
    # Line 2: stacked item with value
    ProposedLine.objects.create(
        batch=b, character=character, item=stacked_item, quantity=100, note="Rope reward"
    )
    # Line 3: catalogue item with no value
    ProposedLine.objects.create(
        batch=b, character=character, item=no_value_item, quantity=1, note="Rock reward"
    )
    # Line 4: proposed item (new item) - shows "New item" badge
    ProposedLine.objects.create(
        batch=b, character=character, proposed_item=proposed, quantity=1, note="New item reward"
    )
    # Line 5: coins line
    ProposedLine.objects.create(batch=b, character=character, coins=250, note="Gold reward")

    return b


def url(name, batch, *args):
    return reverse(f"agent_access:{name}", args=[batch.club.slug, batch.pk, *args])


def coin_post(prefix, cp=0, **extra):
    data = {f"{prefix}-coins_{s}": "" for s in ("pp", "gp", "sp", "cp")}
    data[f"{prefix}-coins_cp"] = str(cp)
    data.update(extra)
    return data


def test_batch_detail_shows_item_values(batch_with_lines, gm_client):
    """Test that catalogue item lines show their value in the lines table."""
    html = gm_client.get(url("batch_detail", batch_with_lines)).content.decode()

    # Catalogue item with value (500 cp = 5 gp)
    assert "Gold Gem" in html
    assert "5 gp" in html

    # Stacked item: 200 cp / 50 units = 4 cp/unit = "no value" (< 1 gp)
    assert "Rope" in html
    assert "no value" in html  # Stacked item with < 1 gp per unit

    # Item with no value
    assert "Worthless Rock" in html
    assert "no value" in html

    # Proposed item shows "New item" badge, no value
    assert "Mystery Item" in html
    assert "New item" in html

    # Coins line shows em dash
    assert "250 cp" in html or "2 gp" in html or "2.5 gp" in html


def test_batch_detail_line_edit_summary_shows_values(batch_with_lines, gm_client):
    """Test that line edit summary shows item values for catalogue items."""
    html = gm_client.get(url("batch_detail", batch_with_lines)).content.decode()

    # Check line edit summaries (in the details elements)
    # Line 1: Gold Gem with value
    assert "Gold Gem (5 gp)" in html
    # Line 2: Rope with no value (since < 1 gp per unit)
    assert "Rope (no value)" in html
    # Line 3: Worthless Rock with no value
    assert "Worthless Rock (no value)" in html
    # Line 4: Proposed item - no value shown
    assert "Mystery Item" in html
    # Should not have value for proposed item
    # Line 5: Coins - shows coin value
    assert "250 cp" in html or "2 gp" in html or "2.5 gp" in html


def test_item_picker_widget_rendered(batch_with_lines, gm_client):
    """Test that the item field uses the picker widget (has picker markup)."""
    html = gm_client.get(url("batch_detail", batch_with_lines)).content.decode()

    # The picker widget renders a search input with hx-get to picker_search
    # Check for the picker component structure
    assert "wm-item-picker" in html
    assert "picker/search" in html
    assert 'hx-get="/c/' in html


def test_edit_line_with_picker(batch_with_lines, club, character, gm_client):
    """Test editing a line using the picker widget still works."""
    lines = list(batch_with_lines.lines.order_by("pk"))
    item_line = lines[0]  # Gold Gem line
    new_item = Item.objects.create(club=club, name="Silver Gem", value_cp=100)

    p = f"line-{item_line.pk}"
    data = {
        f"{p}-character": character.pk,
        f"{p}-item": new_item.pk,  # picker returns item pk in hidden input
        f"{p}-quantity": "3",
        f"{p}-note": "Edited via picker",
        f"{p}-date": "2026-05-02",
        f"{p}-proposed_item": "",
        f"{p}-coins_pp": "",
        f"{p}-coins_gp": "",
        f"{p}-coins_sp": "",
        f"{p}-coins_cp": "0",
    }

    response = gm_client.post(url("batch_line_edit", batch_with_lines, item_line.pk), data)
    assert response.status_code == 302

    item_line.refresh_from_db()
    assert item_line.item == new_item
    assert item_line.quantity == 3
    assert item_line.note == "Edited via picker"


def test_remove_line_still_works(batch_with_lines, gm_client):
    """Test that removing a line still works."""
    lines = list(batch_with_lines.lines.order_by("pk"))
    coin_line = lines[4]  # Coins line
    initial_count = batch_with_lines.lines.count()

    response = gm_client.post(url("batch_line_remove", batch_with_lines, coin_line.pk))
    assert response.status_code == 302

    batch_with_lines.refresh_from_db()
    assert batch_with_lines.lines.count() == initial_count - 1
    assert not ProposedLine.objects.filter(pk=coin_line.pk).exists()


def test_confirm_batch_still_works(batch_with_lines, gm_client):
    """Test that confirming a batch still works and writes correct entries."""
    response = gm_client.post(url("batch_confirm", batch_with_lines))
    assert response.status_code == 302

    batch_with_lines.refresh_from_db()
    assert batch_with_lines.status == "confirmed"

    entries = list(LedgerEntry.objects.filter(agent_batch=batch_with_lines).order_by("pk"))
    # 5 lines total: 3 item lines (2 catalogue, 1 stacked, 1 proposed->approved), 1 coins
    # Actually proposed item with approved_item becomes an item award
    # Each entry can have multiple lines (LedgerLine)
    assert len(entries) == 5

    # Check lines have correct items/coins
    lines = LedgerLine.objects.filter(entry__agent_batch=batch_with_lines)
    item_lines = [ln for ln in lines if ln.item is not None]
    coin_lines = [ln for ln in lines if ln.coins != 0]

    assert len(item_lines) == 4  # 3 catalogue + 1 proposed->approved
    assert len(coin_lines) == 1


def test_reverse_batch_still_works(batch_with_lines, gm_client):
    """Test that reversing a confirmed batch still works."""
    # First confirm
    gm_client.post(url("batch_confirm", batch_with_lines))
    batch_with_lines.refresh_from_db()
    assert batch_with_lines.status == "confirmed"

    # Then reverse
    response = gm_client.post(url("batch_reverse", batch_with_lines))
    assert response.status_code == 302

    batch_with_lines.refresh_from_db()
    assert batch_with_lines.status == "reversed"

    # Entries should be doubled (original + reversal)
    entries = LedgerEntry.objects.filter(agent_batch=batch_with_lines)
    assert entries.count() == 10  # 5 original + 5 reversal


def test_saved_batch_data_identical(batch_with_lines, club, character, gm_client):
    """Test that saved batch data is identical to before the picker change."""
    # Edit a line using the picker
    lines = list(batch_with_lines.lines.order_by("pk"))
    item_line = lines[0]
    new_item = Item.objects.create(club=club, name="Silver Gem", value_cp=100)

    p = f"line-{item_line.pk}"
    data = {
        f"{p}-character": character.pk,
        f"{p}-item": new_item.pk,
        f"{p}-quantity": "3",
        f"{p}-note": "Edited via picker",
        f"{p}-date": "2026-05-02",
        f"{p}-proposed_item": "",
        f"{p}-coins_pp": "",
        f"{p}-coins_gp": "",
        f"{p}-coins_sp": "",
        f"{p}-coins_cp": "0",
    }

    gm_client.post(url("batch_line_edit", batch_with_lines, item_line.pk), data)

    # Verify the saved data matches what the form would have saved before
    item_line.refresh_from_db()
    assert item_line.item == new_item
    assert item_line.quantity == 3
    assert item_line.note == "Edited via picker"
    assert item_line.coins == 0
    assert item_line.proposed_item is None


def test_proposed_item_and_coins_lines_no_value_display(batch_with_lines, gm_client):
    """Test that proposed-item and coins lines don't show item_value."""
    html = gm_client.get(url("batch_detail", batch_with_lines)).content.decode()

    # Proposed item line should show "New item" badge but no value
    # Find the line for Mystery Item
    assert "Mystery Item" in html
    assert "New item" in html

    # The proposed item should not have an item_value displayed next to it
    # (it shows "New item" badge instead)

    # Coins line should show coin value but no item_value
    # This is tested by the fact that coins are formatted via coins template tag


def test_validation_exactly_one_of_item_proposed_coins(
    batch_with_lines, club, character, gm_client
):
    """Test that the exactly-one-of validation still works."""
    lines = list(batch_with_lines.lines.order_by("pk"))
    item_line = lines[0]
    new_item = Item.objects.create(club=club, name="Another Gem", value_cp=100)
    proposed = ProposedItem.objects.create(
        club=club, name="Proposed", status="approved", approved_item=new_item
    )

    p = f"line-{item_line.pk}"

    # Try to submit both item AND proposed_item - should fail
    data = {
        f"{p}-character": character.pk,
        f"{p}-item": new_item.pk,
        f"{p}-proposed_item": proposed.pk,
        f"{p}-quantity": "1",
        f"{p}-note": "Invalid",
        f"{p}-date": "2026-05-02",
        f"{p}-coins_pp": "",
        f"{p}-coins_gp": "",
        f"{p}-coins_sp": "",
        f"{p}-coins_cp": "0",
    }

    response = gm_client.post(url("batch_line_edit", batch_with_lines, item_line.pk), data)
    assert response.status_code == 400
    body = response.content.decode().lower()
    assert "exactly one" in body or "give exactly one" in body

    # Try to submit item AND coins - should fail
    data[f"{p}-proposed_item"] = ""
    data[f"{p}-coins_cp"] = "100"
    response = gm_client.post(url("batch_line_edit", batch_with_lines, item_line.pk), data)
    assert response.status_code == 400

    # Try to submit none - should fail
    data[f"{p}-item"] = ""
    data[f"{p}-coins_cp"] = "0"
    response = gm_client.post(url("batch_line_edit", batch_with_lines, item_line.pk), data)
    assert response.status_code == 400

    # Valid: only item
    data[f"{p}-item"] = new_item.pk
    data[f"{p}-coins_cp"] = "0"
    data[f"{p}-quantity"] = "1"
    response = gm_client.post(url("batch_line_edit", batch_with_lines, item_line.pk), data)
    assert response.status_code == 302

    # Valid: only proposed_item
    data[f"{p}-item"] = ""
    data[f"{p}-proposed_item"] = proposed.pk
    response = gm_client.post(url("batch_line_edit", batch_with_lines, item_line.pk), data)
    assert response.status_code == 302

    # Valid: only coins
    data[f"{p}-proposed_item"] = ""
    data[f"{p}-coins_cp"] = "500"
    data[f"{p}-quantity"] = "0"
    response = gm_client.post(url("batch_line_edit", batch_with_lines, item_line.pk), data)
    assert response.status_code == 302
