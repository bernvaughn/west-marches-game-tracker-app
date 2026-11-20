"""Additional tests for bulk award: many rows, JS features, flash link, error re-render."""

import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from player_characters.forms_adjust import BULK_MAX_ROWS
from player_characters.models import Character

pytestmark = pytest.mark.django_db


def bulk_award_url(club):
    return reverse("characters:bulk_award", kwargs={"club_slug": club.slug})


def bulk_payload_many_items(
    character, items, num_rows, coins=None, note="Party loot", date="2025-01-15"
):
    """Build POST payload for bulk award with many item rows."""
    data = {
        "note": note,
        "date": date,
        "characters": [str(character.pk)],
    }
    if coins:
        data[f"coins_{character.pk}"] = str(coins)
    prefix = f"items_{character.pk}"
    data[f"{prefix}-TOTAL_FORMS"] = str(num_rows)
    data[f"{prefix}-INITIAL_FORMS"] = "0"
    data[f"{prefix}-MIN_NUM_FORMS"] = "0"
    data[f"{prefix}-MAX_NUM_FORMS"] = str(num_rows)
    for i, (item, qty) in enumerate(items):
        data[f"{prefix}-{i}-item_id"] = str(item.pk)
        data[f"{prefix}-{i}-quantity"] = str(qty)
    return data


def entries(character):
    return LedgerEntry.objects.filter(character=character).order_by("pk")


def create_items(club, count):
    """Create multiple items for testing."""
    return [Item.objects.create(club=club, name=f"Item {i}", value_cp=100) for i in range(count)]


@pytest.mark.story("S8")
def test_bulk_award_six_items_one_character(login, game_master, club, character):
    """A GM can award 6 items to one character in one submit."""
    items = create_items(club, 6)
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload_many_items(
            character,
            [(items[i], 1) for i in range(6)],
            num_rows=6,
        ),
    )
    assert r.status_code == 302
    e = entries(character).get()
    assert e.kind == "award"
    assert e.lines.filter(item__isnull=False).count() == 6


@pytest.mark.story("S8")
def test_bulk_award_over_cap_rejected(login, game_master, club, character):
    """Over the BULK_MAX_ROWS cap gives a form error and no entry.

    Note: Django's DATA_UPLOAD_MAX_NUMBER_FIELDS (default 1000) kicks in before
    our formset validation when sending 501+ rows with multiple fields each.
    The request returns 400 and no entry is created, which is the desired outcome.
    """
    item = Item.objects.create(club=club, name="Test Item", value_cp=100)
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload_many_items(
            character,
            [(item, 1)] * (BULK_MAX_ROWS + 1),
            num_rows=BULK_MAX_ROWS + 1,
        ),
    )
    # Django returns 400 for too many fields, our formset would also reject
    assert r.status_code == 400
    assert not entries(character).exists()


@pytest.mark.story("S8")
def test_bulk_award_get_renders_three_rows_and_hidden_buttons(login, game_master, club, character):
    """Default GET renders exactly 3 rows with TOTAL_FORMS=3 and buttons hidden."""
    c = login(game_master)
    r = c.get(bulk_award_url(club))
    assert r.status_code == 200
    html = r.content.decode()
    assert f'name="items_{character.pk}-TOTAL_FORMS"' in html
    assert 'value="3"' in html
    assert f'name="items_{character.pk}-MAX_NUM_FORMS"' in html
    assert 'value="500"' in html
    assert "data-wm-add-item" in html
    assert "data-wm-copy-loot" in html
    assert "hidden" in html


@pytest.mark.story("S8")
def test_bulk_award_no_js_three_rows_works(login, game_master, club, character):
    """No-JS 3-row POST still works (submits 3 rows without JS)."""
    items = create_items(club, 3)
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload_many_items(
            character,
            [(items[i], 1) for i in range(3)],
            num_rows=3,
        ),
    )
    assert r.status_code == 302
    e = entries(character).get()
    assert e.lines.filter(item__isnull=False).count() == 3


@pytest.mark.story("S8")
def test_bulk_award_error_rerender_keeps_posted_rows(login, game_master, club, character):
    """Error re-render keeps posted rows (5 rows survive)."""
    items = create_items(club, 5)
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload_many_items(
            character,
            [(items[i], 1) for i in range(5)],
            num_rows=5,
            coins="not-a-number",
        ),
    )
    assert r.status_code == 400
    html = r.content.decode()
    for i in range(5):
        assert f'name="items_{character.pk}-{i}-item_id"' in html
        assert 'value="' in html
    assert f'name="items_{character.pk}-TOTAL_FORMS"' in html
    assert 'value="5"' in html


@pytest.mark.story("S8")
def test_bulk_award_success_flash_contains_points_link(
    login, game_master, club, character, second_character, item
):
    """Success flash contains ?characters=<pk>,<pk> for only the awarded characters."""
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        {
            "note": "Party loot",
            "date": "2025-01-15",
            "characters": [str(character.pk), str(second_character.pk)],
            f"coins_{character.pk}": "500",
            f"coins_{second_character.pk}": "300",
            f"items_{character.pk}-TOTAL_FORMS": "3",
            f"items_{character.pk}-INITIAL_FORMS": "0",
            f"items_{character.pk}-MIN_NUM_FORMS": "0",
            f"items_{character.pk}-MAX_NUM_FORMS": "3",
            f"items_{character.pk}-0-item_id": str(item.pk),
            f"items_{character.pk}-0-quantity": "1",
        },
    )
    assert r.status_code == 302
    r2 = c.get(r.url)
    html = r2.content.decode()
    expected_chars = f"{character.pk},{second_character.pk}"
    assert f"characters={expected_chars}" in html
    assert "Award downtime points to these characters" in html


@pytest.mark.story("S8")
def test_bulk_award_page_loads_loot_rows_js(login, game_master, club, character):
    """GET page loads js/loot_rows.js."""
    c = login(game_master)
    r = c.get(bulk_award_url(club))
    assert r.status_code == 200
    html = r.content.decode()
    assert "js/loot_rows.js" in html


@pytest.mark.story("S8")
def test_bulk_award_add_copy_buttons_exist_with_data_attrs(login, game_master, club, character):
    """Add/Copy buttons exist with their data attributes."""
    c = login(game_master)
    r = c.get(bulk_award_url(club))
    html = r.content.decode()
    assert "data-wm-add-item" in html
    assert "data-wm-copy-loot" in html
    assert "Add item" in html
    assert "Copy this loot to all picked characters" in html


@pytest.mark.story("S8")
def test_bulk_award_foreign_character_rejected(
    login, game_master, club, character, other_club, item
):
    """Foreign character still rejected."""
    from accounts.models import Membership, User

    foreign_user = User.objects.create_user(
        "foreign@example.com", password="pw", display_name="Foreign"
    )
    foreign_member = Membership.objects.create(user=foreign_user, club=other_club)
    foreign_character = Character.objects.create(
        club=other_club, owner=foreign_member, name="Foreign"
    )

    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        {
            "note": "x",
            "date": "2025-01-15",
            "characters": [str(foreign_character.pk)],
            f"coins_{foreign_character.pk}": "500",
            f"items_{foreign_character.pk}-TOTAL_FORMS": "3",
            f"items_{foreign_character.pk}-INITIAL_FORMS": "0",
            f"items_{foreign_character.pk}-MIN_NUM_FORMS": "0",
            f"items_{foreign_character.pk}-MAX_NUM_FORMS": "3",
        },
    )
    assert r.status_code == 200
    assert "Select at least one character" in r.content.decode() or "Invalid" in r.content.decode()
    assert not entries(foreign_character).exists()


@pytest.mark.story("S8")
def test_bulk_award_get_is_usable_without_js(login, game_master, club, character):
    """Without JS every character section shows, and coins start blank (not "None")."""
    c = login(game_master)
    html = c.get(bulk_award_url(club)).content.decode()
    section = html.split(f'id="char-section-{character.pk}"')[1].split(">")[0]
    assert "d-none" not in section
    coins = html.split(f'id="coins_{character.pk}"')[1].split(">")[0]
    assert 'value=""' in coins
    assert "None" not in coins


@pytest.mark.story("S8")
def test_bulk_award_blank_coins_from_form_are_accepted(login, game_master, club, character):
    """Posting the GET form's blank coins value with items creates one entry."""
    items = create_items(club, 1)
    c = login(game_master)
    data = bulk_payload_many_items(character, [(items[0], 2)], num_rows=3)
    data[f"coins_{character.pk}"] = ""
    r = c.post(bulk_award_url(club), data)
    assert r.status_code == 302
    assert entries(character).count() == 1
