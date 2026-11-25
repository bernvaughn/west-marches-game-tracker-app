"""Tests for the container open result template (S1: Server markup and no-animation view)."""

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from items.containers import loot_preview
from items.models import Item
from items.opening import open_container, opening_view_model
from items.tests.factories import add_slot, make_container
from ledger.services import Line, record

pytestmark = pytest.mark.django_db


def open_url(club, character, item):
    return reverse(
        "characters:open_container",
        kwargs={"club_slug": club.slug, "pk": character.pk, "item_pk": item.pk},
    )


def award(character, item, quantity=1, actor=None):
    return record(character, "award", [Line(item=item, quantity=quantity)], actor=actor)


def fixed_container(club, name="Pack", item_name="Rope"):
    container = make_container(club, name=name)
    item = Item.objects.create(club=club, name=item_name, value_cp=1)
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100)
    return container, item


# ---------------------------------------------------------------------------
# Template rendering tests (direct template render)
# ---------------------------------------------------------------------------


def test_result_modal_shows_container_icon_with_symbol(club):
    """Modal shows container's symbol when set."""
    container = make_container(club, "Magic Chest")
    container.symbol = "🎁"
    container.save()
    sword = Item.objects.create(club=club, name="Sword", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)

    html = render_to_string(
        "player_characters/characters/_open_result_body.html",
        {"container": container, "rows": [{"item": sword, "qty": 1}], "error": None},
    )
    assert 'data-fanfare data-container-icon="🎁"' in html
    assert '<span class="wm-fanfare-container-icon" aria-hidden="true">🎁</span>' in html


def test_result_modal_shows_default_container_icon_when_none(club):
    """Modal shows default 📦 when container has no symbol."""
    container = make_container(club, "Plain Box")
    container.symbol = ""
    container.save()
    sword = Item.objects.create(club=club, name="Sword", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)

    html = render_to_string(
        "player_characters/characters/_open_result_body.html",
        {"container": container, "rows": [{"item": sword, "qty": 1}], "error": None},
    )
    assert 'data-fanfare data-container-icon="📦"' in html
    assert '<span class="wm-fanfare-container-icon" aria-hidden="true">📦</span>' in html


def test_result_modal_shows_all_rolled_items_with_icons_names_quantities(club):
    """All rolled items displayed with icon, name, quantity."""
    container = make_container(club, "Loot Box")
    container.symbol = "📦"
    container.save()
    sword = Item.objects.create(club=club, name="Sword", symbol="⚔️", value_cp=100)
    shield = Item.objects.create(club=club, name="Shield", symbol="🛡️", value_cp=80)
    add_slot(container, [(sword, 2, 2, 1)], chance_pct=100, position=0)
    add_slot(container, [(shield, 1, 1, 1)], chance_pct=100, position=1)

    rows = [
        {"item": sword, "qty": 2},
        {"item": shield, "qty": 1},
    ]
    html = render_to_string(
        "player_characters/characters/_open_result_body.html",
        {"container": container, "rows": rows, "error": None},
    )
    # Check container icon
    assert 'data-container-icon="📦"' in html
    # Check first item: qty 2, icon ⚔️, name Sword
    assert "+2" in html
    assert "⚔️" in html
    assert "Sword" in html
    # Check second item: qty 1, icon 🛡️, name Shield
    assert "+1" in html
    assert "🛡️" in html
    assert "Shield" in html
    # Check items are in a row (list items)
    assert html.count("data-wm-reveal-item") == 2


def test_empty_result_shows_friendly_message(club):
    """Empty result shows 'Nothing was inside.' message."""
    container = make_container(club, "Empty Box")
    container.symbol = "📦"
    container.save()

    html = render_to_string(
        "player_characters/characters/_open_result_body.html",
        {"container": container, "rows": [], "error": None},
    )
    assert "Nothing was inside." in html
    assert 'class="wm-sheet-note"' in html
    # Container icon should still be present
    assert 'data-container-icon="📦"' in html


def test_no_js_markup_complete(club):
    """Full result renders without JavaScript (no animation classes, items visible)."""
    container = make_container(club, "Test Chest")
    container.symbol = "🎁"
    container.save()
    sword = Item.objects.create(club=club, name="Sword", symbol="⚔️", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)

    html = render_to_string(
        "player_characters/characters/_open_result_body.html",
        {"container": container, "rows": [{"item": sword, "qty": 1}], "error": None},
    )
    # Should have data-fanfare container
    assert "data-fanfare" in html
    # Should have chest (hidden by default via CSS for no-JS)
    assert 'class="wm-chest"' in html
    # Should have reveal area with items
    assert "data-wm-reveal" in html
    assert "data-wm-reveal-item" in html
    assert "+1" in html
    assert "Sword" in html
    # Should have live region
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert "data-wm-live" in html
    # Should NOT have the armed class (that's added by JS)
    assert "wm-reveal--armed" not in html


def test_preview_never_leaks_unknown_items(club):
    """Preview page (loot_preview with viewer_can_see_unknown=False) never
    contains unknown slot's real item icon or name."""
    container = make_container(club, "Mystery Box")
    sword = Item.objects.create(club=club, name="Secret Sword", symbol="⚔️", value_cp=100)
    # Unknown slot - hidden from players
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100, unknown=True)

    # Player view - unknowns masked
    preview = loot_preview(container, viewer_can_see_unknown=False)

    assert len(preview) == 1
    row = preview[0]
    assert row.masked is True
    assert row.label == "???"
    assert row.item is None

    # Render the preview template
    html = render_to_string("items/_loot_preview.html", {"rows": preview})
    # Should show ??? not the real name
    assert "???" in html
    assert "Secret Sword" not in html
    assert "⚔️" not in html
    # Should not have the real item's symbol anywhere
    assert "wm-item-symbol" not in html or "Secret Sword" not in html


def test_preview_reveals_unknown_items_for_gm(club):
    """Preview page with viewer_can_see_unknown=True reveals unknown slot items."""
    container = make_container(club, "Mystery Box")
    sword = Item.objects.create(club=club, name="Secret Sword", symbol="⚔️", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100, unknown=True)

    # GM view - unknowns revealed
    preview = loot_preview(container, viewer_can_see_unknown=True)

    assert len(preview) == 1
    row = preview[0]
    assert row.masked is False
    assert row.item == sword
    assert row.label == "Secret Sword"

    # Render the preview template
    html = render_to_string("items/_loot_preview.html", {"rows": preview})
    assert "Secret Sword" in html
    # Preview template doesn't render item symbols, only names
    assert "???" not in html


# ---------------------------------------------------------------------------
# Integration tests (via view)
# ---------------------------------------------------------------------------


def test_modal_via_view_shows_container_icon(login, player, club, character, club_admin):
    """HTMX modal result shows container icon via view."""
    container = make_container(club, "Test Chest")
    container.symbol = "🎁"
    container.save()
    sword = Item.objects.create(club=club, name="Sword", symbol="⚔️", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)
    award(character, container, actor=club_admin)

    r = login(player).post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    content = r.content.decode()
    assert 'data-fanfare data-container-icon="🎁"' in content
    assert '<span class="wm-fanfare-container-icon" aria-hidden="true">🎁</span>' in content
    assert "⚔️" in content
    assert "Sword" in content


def test_full_page_via_view_shows_container_icon(login, player, club, character, club_admin):
    """Full page result shows container icon via view."""
    container = make_container(club, "Test Chest")
    container.symbol = "🎁"
    container.save()
    sword = Item.objects.create(club=club, name="Sword", symbol="⚔️", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)
    award(character, container, actor=club_admin)

    r = login(player).post(open_url(club, character, container))
    assert r.status_code == 200
    content = r.content.decode()
    assert 'data-fanfare data-container-icon="🎁"' in content
    assert '<span class="wm-fanfare-container-icon" aria-hidden="true">🎁</span>' in content
    assert "⚔️" in content
    assert "Sword" in content


class AlwaysMissRNG:
    """RNG that always makes chance checks miss (returns above range for randint)."""

    def randint(self, a, b):
        return b + 1  # Always above range -> chance check always fails

    def randrange(self, n):
        return 0  # Always pick first option if called


def test_empty_result_via_view_shows_message(login, player, club, character, club_admin):
    """Empty result via view shows friendly message."""
    container = make_container(club, "Empty Box")
    container.symbol = "📦"
    container.save()
    # Slot with 50% chance - AlwaysMissRNG forces the chance check to fail
    nothing = Item.objects.create(club=club, name="Nothing", value_cp=1)
    add_slot(container, [(nothing, 1, 1, 1)], chance_pct=50)
    award(character, container, actor=club_admin)

    # AlwaysMissRNG makes the chance check fail, so no items are rolled
    opening = open_container(character, container, club_admin, rng=AlwaysMissRNG())
    rows = opening_view_model(opening)
    assert rows == []  # Empty result

    # Now test the template renders correctly with empty rows
    html = render_to_string(
        "player_characters/characters/_open_result_body.html",
        {"container": container, "rows": rows, "error": None},
    )
    assert "Nothing was inside." in html
    assert 'data-container-icon="📦"' in html


def test_unknown_item_hidden_before_open_revealed_after(login, player, club, character, club_admin):
    """Unknown item is hidden in preview but revealed after opening."""
    container = make_container(club, "Mystery Box")
    secret = Item.objects.create(club=club, name="Secret Item", symbol="💎", value_cp=500)
    add_slot(container, [(secret, 1, 1, 1)], chance_pct=100, unknown=True)
    award(character, container, actor=club_admin)

    # Preview masks unknown
    preview = loot_preview(container, viewer_can_see_unknown=False)
    html = render_to_string("items/_loot_preview.html", {"rows": preview})
    assert "Secret Item" not in html
    assert "💎" not in html
    assert "???" in html

    # Open reveals the item
    r = login(player).post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    content = r.content.decode()
    assert "Secret Item" in content
    assert "💎" in content


def test_multiple_items_all_shown_in_order(login, player, club, character, club_admin):
    """Multiple items shown in slot order with correct quantities."""
    container = make_container(club, "Multi Box")
    container.symbol = "📦"
    container.save()
    item_a = Item.objects.create(club=club, name="Item A", symbol="🅰️", value_cp=10)
    item_b = Item.objects.create(club=club, name="Item B", symbol="🅱️", value_cp=20)
    item_c = Item.objects.create(club=club, name="Item C", symbol="🅲", value_cp=30)
    add_slot(container, [(item_a, 3, 3, 1)], chance_pct=100, position=0)
    add_slot(container, [(item_b, 2, 2, 1)], chance_pct=100, position=1)
    add_slot(container, [(item_c, 1, 1, 1)], chance_pct=100, position=2)
    award(character, container, actor=club_admin)

    r = login(player).post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    content = r.content.decode()
    # Check all three items appear in order
    assert content.index("🅰️") < content.index("🅱️") < content.index("🅲")
    assert "+3" in content
    assert "+2" in content
    assert "+1" in content


def test_result_modal_shows_container_name(login, player, club, character, club_admin):
    """Modal shows 'You opened [container name]'."""
    container = make_container(club, "Special Chest")
    container.symbol = "🎁"
    container.save()
    sword = Item.objects.create(club=club, name="Sword", value_cp=100)
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100)
    award(character, container, actor=club_admin)

    r = login(player).post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    content = r.content.decode()
    assert "You opened Special Chest" in content
