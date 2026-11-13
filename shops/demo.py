from datetime import date, timedelta

from django.utils import timezone

from items.models import Item

from .models import Rotation, Shop, ShopStock


def _shop(club, name, keeper, stock, rotation_name, open_date, close_date, look):
    shop, created = Shop.objects.get_or_create(
        club=club, name=name, defaults={"keeper_name": keeper, **look}
    )
    # Shops seeded before silhouettes existed still hold the default: give them theirs.
    if not created and shop.silhouette == Shop.Silhouette.HOODED_TRADER and "silhouette" in look:
        shop.silhouette = look["silhouette"]
        shop.save(update_fields=["silhouette"])
    # Same for the street: shops still on the defaults take their building and place.
    if not created and shop.building == Shop.Building.GENERAL_STORE and shop.street_position == 0:
        shop.building = look.get("building", shop.building)
        shop.street_position = look.get("street_position", 0)
        shop.save(update_fields=["building", "street_position"])
    if not shop.description and look.get("description"):
        shop.description = look["description"]
        shop.save(update_fields=["description"])
    for item_name, qty in stock:
        item = Item.objects.get(club=club, name=item_name)
        ShopStock.objects.get_or_create(shop=shop, item=item, defaults={"quantity": qty})
    rotation, _ = Rotation.objects.get_or_create(
        club=club,
        name=rotation_name,
        defaults={"open_date": open_date, "close_date": close_date},
    )
    rotation.shops.add(shop)


def seed(club):
    today = timezone.localdate()
    _shop(
        club,
        "The Rusty Lantern",
        "Old Marta",
        [("Rope", None), ("Torch", None), ("Longsword", 2)],
        "Always open",
        date(2026, 1, 1),
        None,
        {
            "description": (
                "A warm inn at the head of the street. Marta sells rope, torches and the odd blade."
            ),
            "keeper_description": "A broad woman with flour-dusted hands and a sharp eye for coin.",
            "color": "ember",
            "silhouette": "burly_innkeeper",
            "symbol": "🏮",
            "building": "inn",
            "street_position": 1,
        },
    )
    _shop(
        club,
        "Wandering Caravan",
        "Zahra",
        [("Healing potion", 3), ("Moonstone amulet", 1)],
        "This week",
        today - timedelta(days=3),
        today + timedelta(days=4),
        {
            "description": (
                "A caravan of striped tents that rolls in for a week at a time, "
                "heavy with potions and charms."
            ),
            "keeper_description": "A veiled trader who arrives with the dust and leaves by dawn.",
            "color": "violet",
            "silhouette": "veiled_merchant",
            "symbol": "🐪",
            "building": "tent",
            "street_position": 2,
        },
    )
