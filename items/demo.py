from .models import Item

ITEMS = [
    ("Rope", 100, "🪢"),
    ("Healing potion", 5000, "🧪"),
    ("Torch", 1, "🔥"),
    ("Longsword", 1500, "🗡\ufe0f"),
    ("Wolf pelt", 200, "🐺"),
    ("Moonstone amulet", 25000, "🌙"),
]


def seed(club):
    for name, value, symbol in ITEMS:
        item, _ = Item.objects.get_or_create(
            club=club, name=name, defaults={"value_cp": value, "symbol": symbol}
        )
        if not item.symbol:
            item.symbol = symbol
            item.save(update_fields=["symbol"])
