"""Tests for the General Store seeding service."""

import pytest
from django.urls import reverse

from accounts.club_seeding import seed_new_club
from accounts.models import Club, Membership, User
from items.models import Item
from ledger.services import Line, available_coins, item_quantities, record
from player_characters.junk import set_junk
from shops.models import Rotation, Shop, ShopStock
from shops.seeding import GeneralStoreSummary, seed_default_general_store

pytestmark = pytest.mark.django_db


def test_seed_default_general_store_creates_shop(club):
    """Seed creates the General Store with correct fields."""
    summary = seed_default_general_store(club)

    assert summary.shop_created is True
    assert summary.skipped is False

    shop = Shop.objects.get(club=club, name="General Store")
    assert shop.keeper_name == "Mabel Packwell"
    assert "halfling grocer" in shop.keeper_description.lower()
    assert shop.sell_percent == 100
    assert shop.buy_percent == 75
    assert shop.silhouette == Shop.Silhouette.HALFLING_GROCER
    assert shop.building == Shop.Building.GENERAL_STORE
    assert shop.street_position == 0
    assert shop.symbol == "🧺"
    assert shop.color == "parchment"


def test_seed_default_general_store_in_always_open_rotation(club):
    """Shop is added to 'Always open' rotation."""
    seed_default_general_store(club)

    shop = Shop.objects.get(club=club, name="General Store")
    rotation = Rotation.objects.get(club=club, name="Always open")
    assert shop in rotation.shops.all()
    assert rotation.open_date is not None
    assert rotation.close_date is None


def test_seed_default_general_store_stock_unlimited(club):
    """Every gear item has a stock row with unlimited quantity and no price overrides."""
    summary = seed_default_general_store(club)

    shop = Shop.objects.get(club=club, name="General Store")
    stock_rows = ShopStock.objects.filter(shop=shop)

    assert stock_rows.count() == summary.stock_created > 0

    for stock in stock_rows:
        assert stock.quantity is None  # unlimited
        assert stock.sell_percent is None  # no override
        assert stock.buy_percent is None  # no override


def test_seed_default_general_store_stock_names_match_gear_list(club):
    """Stocked item names exactly match the gear list."""
    from shops.gear import GENERAL_STORE_GEAR

    seed_default_general_store(club)

    shop = Shop.objects.get(club=club, name="General Store")
    stocked_names = set(ShopStock.objects.filter(shop=shop).values_list("item__name", flat=True))
    gear_names = {g.name for g in GENERAL_STORE_GEAR}

    assert stocked_names == gear_names


def test_seed_default_general_store_no_weapons_armor_tools_magic(club):
    """No weapon, armor, tool, or magic item is in stock."""

    seed_default_general_store(club)

    shop = Shop.objects.get(club=club, name="General Store")
    stocked_names = set(ShopStock.objects.filter(shop=shop).values_list("item__name", flat=True))

    # These are examples of items that should NOT be in the gear list
    forbidden = {
        "Longsword",
        "Chain Mail",
        "Thieves' Tools",
        "Potion of Healing",
        "Spell Scroll (Cantrip)",
        "Spell Scroll (Level 1)",
        "Leather Armor",
        "Greataxe",
        "Shield",
    }
    assert stocked_names.isdisjoint(forbidden)


def test_seed_default_general_store_idempotent(club):
    """Second call creates no new items, stock rows, shops, or rotations."""
    _summary1 = seed_default_general_store(club)
    summary2 = seed_default_general_store(club)

    assert summary2.skipped is True
    assert summary2.shop_created is False
    assert summary2.items_created == 0
    assert summary2.stock_created == 0

    assert Shop.objects.filter(club=club, name__iexact="General Store").count() == 1
    assert Rotation.objects.filter(club=club, name="Always open").count() == 1


def test_seed_default_general_store_existing_items_untouched(club):
    """Pre-existing items keep their values; no duplicate by name."""
    # Pre-create Ink (1 oz) at a different value
    Item.objects.create(club=club, name="Ink (1 oz)", value_cp=7, symbol="🖋️")
    # Pre-create parchment (10 sheets) with different case
    Item.objects.create(club=club, name="parchment (10 sheets)", value_cp=999, symbol="📜")

    seed_default_general_store(club)

    # Original items should keep their values
    ink = Item.objects.get(club=club, name__iexact="Ink (1 oz)")
    assert ink.value_cp == 7

    parchment = Item.objects.get(club=club, name__iexact="parchment (10 sheets)")
    assert parchment.value_cp == 999

    # No duplicates
    assert Item.objects.filter(club=club, name__iexact="Ink (1 oz)").count() == 1
    assert Item.objects.filter(club=club, name__iexact="parchment (10 sheets)").count() == 1


def test_seed_default_general_store_pre_existing_shop_unchanged(club):
    """Pre-existing shop named 'general store' with its own stock: nothing changes."""
    # Create a shop with different keeper and stock
    existing = Shop.objects.create(
        club=club,
        name="general store",
        keeper_name="Different Keeper",
        sell_percent=90,
        buy_percent=60,
    )
    item = Item.objects.create(club=club, name="Custom Item", value_cp=100, symbol="📦")
    ShopStock.objects.create(shop=existing, item=item, quantity=5)

    summary = seed_default_general_store(club)

    assert summary.skipped is True
    existing.refresh_from_db()
    assert existing.keeper_name == "Different Keeper"
    assert existing.sell_percent == 90
    assert existing.buy_percent == 60
    assert ShopStock.objects.filter(shop=existing, item=item).exists()


def test_seed_default_general_store_retired_item_no_twin(club):
    """Retired item: no twin created, no stock row."""
    Item.objects.create(club=club, name="Rope", value_cp=100, symbol="🪢", retired=True)

    seed_default_general_store(club)

    shop = Shop.objects.get(club=club, name="General Store")
    assert Item.objects.filter(club=club, name__iexact="Rope").count() == 1
    # Should not create a stock row for the retired item
    assert not ShopStock.objects.filter(shop=shop, item__name__iexact="Rope").exists()


def test_seed_default_general_store_rollback_on_failure(site_admin, login, monkeypatch):
    """A General Store seeding failure rolls back the whole new club."""

    def boom(club, **kwargs):
        raise RuntimeError("general store failed")

    monkeypatch.setattr("accounts.club_seeding.seed_default_general_store", boom)
    client = login(site_admin)
    with pytest.raises(RuntimeError):
        client.post(
            reverse("site_club_new"),
            {
                "name": "Club C",
                "slug": "",
                "admin_email": "Boss@Example.com",
                "admin_display_name": "Boss",
            },
        )

    assert not Club.objects.filter(slug="club-c").exists()
    assert not User.objects.filter(email="boss@example.com").exists()
    assert not Membership.objects.filter(user__email="boss@example.com").exists()


def test_seed_default_general_store_keeps_existing_shop_look(club):
    """A pre-existing General Store keeps its own position, building and silhouette."""
    existing = Shop.objects.create(
        club=club,
        name="General Store",
        keeper_name="Someone Else",
        building=Shop.Building.INN,
        silhouette=Shop.Silhouette.HOODED_TRADER,
        street_position=5,
    )

    summary = seed_default_general_store(club)

    assert summary.skipped is True
    existing.refresh_from_db()
    assert existing.building == Shop.Building.INN
    assert existing.silhouette == Shop.Silhouette.HOODED_TRADER
    assert existing.street_position == 5
    assert not existing.stock.exists()
    assert not Rotation.objects.filter(club=club, name="Always open").exists()


def test_seed_new_club_includes_general_store(club):
    """seed_new_club returns general_store in result dict."""
    result = seed_new_club(club)

    assert "general_store" in result
    assert isinstance(result["general_store"], GeneralStoreSummary)
    assert result["general_store"].shop_created is True


def test_seed_new_club_creates_shop(club):
    """New club has a General Store."""
    seed_new_club(club)

    assert Shop.objects.filter(club=club, name="General Store").exists()
    shop = Shop.objects.get(club=club, name="General Store")
    assert shop.keeper_name == "Mabel Packwell"
    assert shop.sell_percent == 100
    assert shop.buy_percent == 75
    assert shop.street_position == 0


def test_seed_new_club_shop_in_open_shops_today(club):
    """General Store appears in open_shops today."""
    from django.utils import timezone

    from shops.services import open_shops

    seed_new_club(club)

    today = timezone.localdate()
    open = open_shops(club, today)
    assert open.filter(name="General Store").exists()


def test_seed_new_club_shop_first_in_ordered_shops(club):
    """General Store is first in ordered_shops (position 0)."""
    from shops.services import ordered_shops

    seed_new_club(club)

    shops = ordered_shops(Shop.objects.for_club(club))
    assert shops.first().name == "General Store"


def test_gear_list_prices_match_book(club):
    """Pin a few key book prices."""
    from shops.gear import GENERAL_STORE_GEAR

    gear_dict = {g.name: g.value_cp for g in GENERAL_STORE_GEAR}

    assert gear_dict["Rope"] == 100  # 1 gp
    assert gear_dict["Backpack"] == 200  # 2 gp
    assert gear_dict["Spyglass"] == 100000  # 1,000 gp
    assert gear_dict["Arrows"] == 100  # 1 gp for 20 arrows (stacked, value_units=20)


def test_gear_list_no_duplicate_names(club):
    """No duplicate names (casefold) in gear list."""
    from shops.gear import GENERAL_STORE_GEAR

    names = [g.name.casefold() for g in GENERAL_STORE_GEAR]
    assert len(names) == len(set(names))


def test_gear_list_all_values_positive(club):
    """Every gear value > 0."""
    from shops.gear import GENERAL_STORE_GEAR

    for g in GENERAL_STORE_GEAR:
        assert g.value_cp > 0, f"{g.name} has non-positive value"


def test_gear_list_overlap_with_starting_equipment(club):
    """Gear-list prices agree with starting-equipment constants for shared names."""
    # This test will be run after starting_equipment/seeding.py is updated
    from shops.gear import GENERAL_STORE_GEAR
    from starting_equipment.seeding import BACKGROUND_EQUIPMENT, CLASS_EQUIPMENT

    gear_dict = {g.name: g.value_cp for g in GENERAL_STORE_GEAR}

    # Collect all starting equipment item names and values
    se_values = {}
    for class_data in CLASS_EQUIPMENT.values():
        for item_data in class_data["items"]:
            name = item_data[0]
            value = item_data[1]
            if name not in se_values:
                se_values[name] = value

    for bg_data in BACKGROUND_EQUIPMENT.values():
        for item_data in bg_data["items"]:
            name = item_data[0]
            value = item_data[1]
            if name not in se_values:
                se_values[name] = value

    # Check overlap - prices should match
    for name, value in se_values.items():
        if name in gear_dict:
            assert gear_dict[name] == value, (
                f"Price mismatch for {name}: gear={gear_dict[name]}, starting_equipment={value}"
            )


def test_buy_and_sell_at_shop(club, player, character, login):
    """A player buys Rope for 100 cp and sells a 100 cp junk item for 75 cp."""
    seed_default_general_store(club)
    shop = Shop.objects.get(club=club, name="General Store")
    rope_stock = ShopStock.objects.get(shop=shop, item__name="Rope")
    junk = Item.objects.create(club=club, name="Old Lute", value_cp=100)
    record(character, "award", [Line(coins=1000), Line(item=junk, quantity=1)])
    set_junk(character, junk, 1, player)
    client = login(player)

    resp = client.post(
        reverse("shops:buy", args=[club.slug, shop.pk, rope_stock.pk]),
        {"character": character.pk, "quantity": 1},
    )
    assert resp.status_code == 302
    assert available_coins(character) == 900
    assert item_quantities(character)[rope_stock.item_id] == 1
    rope_stock.refresh_from_db()
    assert rope_stock.quantity is None  # still unlimited

    resp = client.post(
        reverse("shops:sell_junk", args=[club.slug, shop.pk]),
        {"item": [junk.pk], f"qty_{junk.pk}": "1"},
    )
    assert resp.status_code == 302
    assert available_coins(character) == 975
    assert item_quantities(character).get(junk.pk, 0) == 0


def test_demo_club_has_general_store(club):
    """Demo club seeding includes the General Store at position 0."""
    from items.demo import seed as seed_items
    from shops.demo import seed

    seed_items(club)
    seed(club)

    shops = Shop.objects.for_club(club).order_by("street_position")
    assert shops.count() == 3
    assert shops[0].name == "General Store"
    assert shops[0].street_position == 0
    assert shops[1].name == "The Rusty Lantern"
    assert shops[1].street_position == 1
    assert shops[2].name == "Wandering Caravan"
    assert shops[2].street_position == 2

    # Demo items (Rope, Torch) should match the gear list and be kept
    rope = Item.objects.get(club=club, name="Rope")
    torch = Item.objects.get(club=club, name="Torch")
    assert rope.value_cp == 100
    assert torch.value_cp == 1


def test_demo_seed_idempotent(club):
    """Running demo seed twice creates only one General Store."""
    from items.demo import seed as seed_items
    from shops.demo import seed

    seed_items(club)
    seed(club)
    seed(club)

    assert Shop.objects.filter(club=club, name="General Store").count() == 1
    assert Shop.objects.for_club(club).count() == 3
