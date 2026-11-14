import pytest
from django.urls import reverse
from django.utils import timezone

from items.models import Item
from ledger.models import LedgerEntry, LedgerLine
from player_characters.item_cards import CARD_CAP

pytestmark = [pytest.mark.story("U92"), pytest.mark.django_db]


def url(name, club, **q):
    base = reverse(f"items:{name}", args=[club.slug])
    return base + ("?" + "&".join(f"{k}={v}" for k, v in q.items()) if q else "")


def get(login, user, url):
    r = login(user).get(url)
    return r, r.content.decode()


# permissions
def test_picker_denies_player(login, club, player, item):
    r, _ = get(login, player, url("loot_cards_picker", club))
    assert r.status_code == 403


def test_picker_allows_gm(login, club, game_master, item):
    r, _ = get(login, game_master, url("loot_cards_picker", club))
    assert r.status_code == 200


def test_picker_allows_club_admin(login, club, club_admin, item):
    r, _ = get(login, club_admin, url("loot_cards_picker", club))
    assert r.status_code == 200


def test_print_denies_player(login, club, player, item):
    r, _ = get(login, player, url("loot_cards_print", club, **{f"qty_{item.pk}": 1}))
    assert r.status_code == 403


def test_print_allows_gm(login, club, game_master, item):
    r, _ = get(login, game_master, url("loot_cards_print", club, **{f"qty_{item.pk}": 1}))
    assert r.status_code == 200


def test_print_allows_club_admin(login, club, club_admin, item):
    r, _ = get(login, club_admin, url("loot_cards_print", club, **{f"qty_{item.pk}": 1}))
    assert r.status_code == 200


# picker content
def test_picker_lists_items_with_qty_zero(login, club, game_master, item):
    other = Item.objects.create(club=club, name="Torch", value_cp=1)
    r, body = get(login, game_master, url("loot_cards_picker", club))
    assert "Rope" in body and "Torch" in body
    assert f'name="qty_{item.pk}"' in body
    assert f'name="qty_{other.pk}"' in body
    assert 'value="0"' in body


def test_picker_search_filters(login, club, game_master, item):
    Item.objects.create(club=club, name="Torch", value_cp=1)
    r, body = get(login, game_master, url("loot_cards_picker", club, q="Rope"))
    assert "Rope" in body
    assert "Torch" not in body


def test_picker_copies_choice_present(login, club, game_master, item):
    r, body = get(login, game_master, url("loot_cards_picker", club))
    assert "One card per item type" in body
    assert "One card per item" in body
    assert 'name="copies"' in body


# print page
def test_print_skips_qty_zero(login, club, game_master, item):
    other = Item.objects.create(club=club, name="Torch", value_cp=1)
    r, body = get(login, game_master, url("loot_cards_print", club, **{f"qty_{item.pk}": 1, f"qty_{other.pk}": 0}))
    assert "Rope" in body
    assert "Torch" not in body


def test_print_copies_type(login, club, game_master, item):
    r, body = get(login, game_master, url("loot_cards_print", club, copies="type", **{f"qty_{item.pk}": 5}))
    assert body.count('<article class="wm-item-card wm-pass') == 1
    assert "<strong>Used</strong>" in body
    assert body.count('class="wm-use-circle"') == 5


def test_print_copies_item(login, club, game_master, item):
    r, body = get(login, game_master, url("loot_cards_print", club, copies="item", **{f"qty_{item.pk}": 3}))
    assert body.count('<article class="wm-item-card wm-pass') == 3
    assert body.count('<span class="wm-pill-value">1</span>') >= 3
    assert body.count('class="wm-use-circle"') == 3


def test_print_cap_message(login, club, game_master, item):
    r, body = get(login, game_master, url("loot_cards_print", club, copies="item", **{f"qty_{item.pk}": CARD_CAP + 1}))
    assert "more than 90 cards" in body
    assert '<article class="wm-item-card wm-pass' not in body


def test_print_cap_exactly_ok(login, club, game_master, item):
    r, body = get(login, game_master, url("loot_cards_print", club, copies="item", **{f"qty_{item.pk}": CARD_CAP}))
    assert body.count('<article class="wm-item-card wm-pass') == 90
    assert body.count('<section class="wm-card-sheet">') == 10


def test_print_footer_loot_and_date(login, club, game_master, item):
    r, body = get(login, game_master, url("loot_cards_print", club, **{f"qty_{item.pk}": 1}))
    today = timezone.localdate().strftime("%Y-%m-%d")
    assert f"Loot · printed {today}" in body
    assert "Maya" not in body  # no character name


def test_print_no_ledger_or_inventory_changes(login, club, game_master, item, character):
    before_entries = LedgerEntry.objects.filter(club=club).count()
    before_lines = LedgerLine.objects.filter(entry__club=club).count()
    r, _ = get(login, game_master, url("loot_cards_print", club, copies="item", **{f"qty_{item.pk}": 5}))
    assert r.status_code == 200
    assert LedgerEntry.objects.filter(club=club).count() == before_entries
    assert LedgerLine.objects.filter(entry__club=club).count() == before_lines
    # inventory unchanged - character still has 0 of this item
    from player_characters.inventory import inventory_rows
    rows = inventory_rows(character)
    assert all(r.owned == 0 for r in rows)


# cross-club isolation
def test_cross_club_picker_isolation(login, club, other_club, game_master, item):
    foreign = Item.objects.create(club=other_club, name="Foreign", value_cp=10)
    r, body = get(login, game_master, url("loot_cards_picker", club))
    assert "Rope" in body
    assert "Foreign" not in body


def test_cross_club_print_isolation(login, club, other_club, game_master, item):
    foreign = Item.objects.create(club=other_club, name="Foreign", value_cp=10)
    r = login(game_master).get(url("loot_cards_print", club, **{f"qty_{foreign.pk}": 1}))
    # foreign item not in this club's queryset, so qty ignored - no cards printed
    assert r.status_code == 200
    body = r.content.decode()
    assert "Foreign" not in body
    assert "No items selected" in body or "wm-item-card" not in body


# catalogue page has action
def test_catalogue_has_print_loot_action_for_admin(login, club, club_admin, item):
    r, body = get(login, club_admin, url("index", club))
    assert "Print loot cards" in body
    assert url("loot_cards_picker", club) in body


def test_catalogue_has_print_loot_action_for_gm(login, club, game_master, item):
    r, body = get(login, game_master, url("index", club))
    assert "Print loot cards" in body
    assert url("loot_cards_picker", club) in body


def test_catalogue_no_print_loot_action_for_player(login, club, player, item):
    r, body = get(login, player, url("index", club))
    assert "Print loot cards" not in body


# bad copies param defaults to type
def test_bad_copies_defaults_to_type(login, club, game_master, item):
    r, body = get(login, game_master, url("loot_cards_print", club, copies="bogus", **{f"qty_{item.pk}": 1}))
    assert r.status_code == 200
    assert body.count('<article class="wm-item-card wm-pass') == 1