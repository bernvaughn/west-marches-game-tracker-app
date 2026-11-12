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
            "keeper_description": "A broad woman with flour-dusted hands and a sharp eye for coin.",
            "color": "ember",
            "silhouette": "burly_innkeeper",
            "symbol": "🏮",
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
            "keeper_description": "A veiled trader who arrives with the dust and leaves by dawn.",
            "color": "violet",
            "silhouette": "veiled_merchant",
            "symbol": "🐪",
        },
    )
