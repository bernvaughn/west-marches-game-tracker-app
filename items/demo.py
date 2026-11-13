from .models import Item

ITEMS = [
    ("Rope", 100, "🪢", "standard"),
    ("Healing potion", 5000, "🧪", "common"),
    ("Torch", 1, "🔥", "trivial"),
    ("Longsword", 1500, "🗡\ufe0f", "fine"),
    ("Wolf pelt", 200, "🐺", "standard"),
    ("Moonstone amulet", 25000, "🌙", "uncommon"),
]


def seed(club):
    for name, value, symbol, rarity in ITEMS:
        item, _ = Item.objects.get_or_create(
            club=club, name=name, defaults={"value_cp": value, "symbol": symbol, "rarity": rarity}
        )
        if not item.symbol:
            item.symbol = symbol
            item.save(update_fields=["symbol"])
        if rarity and not item.rarity:
            item.rarity = rarity
            item.save(update_fields=["rarity"])
