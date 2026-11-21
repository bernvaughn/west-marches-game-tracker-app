from .models import Item

ITEMS = [
    ("Rope", 100, "🪢", "standard", "", ""),
    ("Healing potion", 5000, "🧪", "common", "potion", ""),
    ("Torch", 1, "🔥", "trivial", "", ""),
    ("Longsword", 1500, "🗡️", "fine", "", ""),
    ("Wolf pelt", 200, "🐺", "standard", "", ""),
    (
        "Moonstone amulet",
        25000,
        "🌙",
        "uncommon",
        "wondrous",
        "Cursed: whispers at night, bearer has disadvantage on Wisdom saves.",
    ),
]

# Stacked items for U123-U131 demo (unit_name, value_units: value_cp covers this many units)
STACKED_ITEMS = [
    (
        "Parchment",
        100,
        "📜",
        "trivial",
        "",
        "",
        True,
        "sheet",
        10,
    ),  # 10 sheets = 100 cp
    (
        "Hempen cord",
        100,
        "🧵",
        "trivial",
        "",
        "",
        True,
        "ft",
        50,
    ),  # 50 ft = 100 cp
]


def seed(club):
    for name, value, symbol, rarity, magic_type, gm_details in ITEMS:
        item, _ = Item.objects.get_or_create(
            club=club,
            name=name,
            defaults={
                "value_cp": value,
                "symbol": symbol,
                "rarity": rarity,
                "magic_type": magic_type,
                "gm_details": gm_details,
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
        if gm_details and not item.gm_details:
            item.gm_details = gm_details
            item.save(update_fields=["gm_details"])

    # Stacked items (is_stacked=True, unit_name, value_units)
    for (
        name,
        value,
        symbol,
        rarity,
        magic_type,
        gm_details,
        is_stacked,
        unit_name,
        value_units,
    ) in STACKED_ITEMS:
        item, _ = Item.objects.get_or_create(
            club=club,
            name=name,
            defaults={
                "value_cp": value,
                "symbol": symbol,
                "rarity": rarity,
                "magic_type": magic_type,
                "gm_details": gm_details,
                "is_stacked": is_stacked,
                "unit_name": unit_name,
                "value_units": value_units,
            },
        )
        # Update stacked fields if they were blank on an existing row
        updated = []
        if item.is_stacked != is_stacked:
            item.is_stacked = is_stacked
            updated.append("is_stacked")
        if not item.unit_name:
            item.unit_name = unit_name
            updated.append("unit_name")
        if item.value_units != value_units:
            item.value_units = value_units
            updated.append("value_units")
        if updated:
            item.save(update_fields=updated)
