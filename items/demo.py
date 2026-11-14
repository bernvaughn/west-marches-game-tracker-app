from .models import Item

ITEMS = [
    ("Rope", 100, "🪢", "standard", ""),
    ("Healing potion", 5000, "🧪", "common", "potion"),
    ("Torch", 1, "🔥", "trivial", ""),
    ("Longsword", 1500, "🗡\ufe0f", "fine", ""),
    ("Wolf pelt", 200, "🐺", "standard", ""),
    ("Moonstone amulet", 25000, "🌙", "uncommon", "wondrous"),
]


def seed(club):
    for name, value, symbol, rarity, magic_type in ITEMS:
        item, _ = Item.objects.get_or_create(
            club=club,
            name=name,
            defaults={
                "value_cp": value,
                "symbol": symbol,
                "rarity": rarity,
                "magic_type": magic_type,
            },
        )
        if not item.symbol:
            item.symbol = symbol
            item.save(update_fields=["symbol"])
        if rarity and not item.rarity:
            item.rarity = rarity
            item.save(update_fields=["rarity"])
        if magic_type and not item.magic_type:
            item.magic_type = magic_type
            item.save(update_fields=["magic_type"])
