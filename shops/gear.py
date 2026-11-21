"""General Store gear list from the 2024 SRD 5.2 Adventuring Gear and Ammunition tables.

Source: https://5e24srd.com/equipment/adventuring-gear.html (mirrors the 2024 PHB).
Ammunition is sold by the book's bundle (e.g., Arrows (20), not per arrow).
Magic rows (Potion of Healing, Spell Scrolls) are excluded.

Stacked items: items whose name in the book includes a count (e.g., "Arrows (20)")
are seeded as a single stacked item with a plain name ("Arrows"), a unit name
("arrow"), and value_units equal to the bundle size. The General Store sells them
as a bundle line of that size at the same total price. Starting equipment grants
the same stacked item in units (e.g., 20 arrows), not a separate plain item.

Item names use the clearer "Variant (Kind)" form from items.seed_names
(VARIANT_RENAMES) so the store catalogue matches the starting-equipment seeds.
"""

from dataclasses import dataclass

from items.seed_names import MAP_CASE, SCROLL_CASE


@dataclass(frozen=True)
class GearItem:
    """A single gear entry.

    Attributes:
        name: Item name as shown in the catalogue (plain name for stacked items).
        value_cp: Total value in copper for `value_units` units (or for the whole
            item if not stacked).
        icon: Emoji symbol.
        description: Short description shown in the catalogue. Defaults to "".
        unit_name: Singular unit name for stacked items (e.g., "arrow"). If
            provided, the item is seeded as stacked with this unit name.
        value_units: How many units the `value_cp` covers for stacked items.
            Default 1 (plain item).
    """

    name: str
    value_cp: int
    icon: str
    description: str = ""
    unit_name: str | None = None
    value_units: int = 1


GENERAL_STORE_GEAR = [
    GearItem("Acid", 2500, "🧪"),
    GearItem("Alchemist's Fire", 5000, "🔥"),
    GearItem("Antitoxin", 5000, "🧪"),
    GearItem("Crystal (Arcane Focus)", 1000, "🔮"),
    GearItem("Orb (Arcane Focus)", 2000, "🔮"),
    GearItem("Rod (Arcane Focus)", 1000, "🪄"),
    GearItem("Staff (Arcane Focus)", 500, "🪄"),
    GearItem("Wand (Arcane Focus)", 1000, "🪄"),
    GearItem("Arrows", 100, "🏹", unit_name="arrow", value_units=20),
    GearItem("Crossbow Bolts", 100, "🏹", unit_name="bolt", value_units=20),
    GearItem("Firearm Bullets", 300, "⚪", unit_name="bullet", value_units=10),
    GearItem("Sling Bullets", 4, "⚪", unit_name="bullet", value_units=20),
    GearItem("Needles", 100, "📌", unit_name="needle", value_units=50),
    GearItem("Backpack", 200, "🎒"),
    GearItem("Ball Bearings", 100, "⚪", unit_name="ball bearing", value_units=1000),
    GearItem("Barrel", 200, "🛢️"),
    GearItem("Basket", 40, "🧺"),
    GearItem("Bedroll", 100, "🛌"),
    GearItem("Bell", 100, "🔔"),
    GearItem("Blanket", 50, "🛌"),
    GearItem("Block and Tackle", 100, "⚙️"),
    GearItem("Book", 2500, "📖"),
    GearItem("Bottle, Glass", 200, "🍾"),
    GearItem("Bucket", 5, "🪣"),
    GearItem("Burglar's Pack", 1600, "🎒"),
    GearItem("Caltrops", 100, "📌", unit_name="caltrop", value_units=20),
    GearItem("Candle", 1, "🕯️"),
    GearItem("Case, Crossbow Bolt", 100, "🧰"),
    GearItem(MAP_CASE, 100, "🗺️", description="Holds rolled maps."),
    GearItem(SCROLL_CASE, 100, "📜", description="Holds scrolls."),
    GearItem("Chain", 500, "⛓️"),
    GearItem("Chest", 500, "🧰"),
    GearItem("Climber's Kit", 2500, "🧗"),
    GearItem("Fine Clothes", 1500, "👔"),
    GearItem("Traveler's Clothes", 200, "👕"),
    GearItem("Component Pouch", 2500, "💼"),
    GearItem("Costume", 500, "🎭"),
    GearItem("Crowbar", 200, "🔨"),
    GearItem("Diplomat's Pack", 3900, "🎒"),
    GearItem("Sprig of Mistletoe (Druidic Focus)", 100, "🌿"),
    GearItem("Staff (Druidic Focus)", 500, "🪄"),
    GearItem("Yew Wand (Druidic Focus)", 1000, "🪄"),
    GearItem("Dungeoneer's Pack", 1200, "🎒"),
    GearItem("Entertainer's Pack", 4000, "🎒"),
    GearItem("Explorer's Pack", 1000, "🎒"),
    GearItem("Flask", 2, "🍶"),
    GearItem("Grappling Hook", 200, "🪝"),
    GearItem("Healer's Kit", 500, "🩹"),
    GearItem("Amulet (Holy Symbol)", 500, "✝️"),
    GearItem("Emblem (Holy Symbol)", 500, "✝️"),
    GearItem("Reliquary (Holy Symbol)", 500, "✝️"),
    GearItem("Holy Water", 2500, "💧"),
    GearItem("Hunting Trap", 500, "🪤"),
    GearItem("Ink (1 oz)", 1000, "🖋️"),
    GearItem("Ink Pen", 2, "🖋️"),
    GearItem("Jug", 2, "🏺"),
    GearItem("Ladder", 10, "🪜"),
    GearItem("Lamp", 50, "🪔"),
    GearItem("Lantern, Bullseye", 1000, "🔦"),
    GearItem("Lantern, Hooded", 500, "🏮"),
    GearItem("Lock", 1000, "🔒"),
    GearItem("Magnifying Glass", 10000, "🔍"),
    GearItem("Manacles", 200, "⛓️"),
    GearItem("Map", 100, "🗺️"),
    GearItem("Mirror", 500, "🪞"),
    GearItem("Net", 100, "🕸️"),
    GearItem("Oil (flask)", 10, "🛢️"),
    GearItem("Paper (one sheet)", 20, "📄"),
    GearItem("Parchment (one sheet)", 10, "📜"),
    GearItem("Perfume (vial)", 500, "🧴"),
    GearItem("Poison, Basic", 10000, "☠️"),
    GearItem("Pole", 5, "📏"),
    GearItem("Pot, Iron", 200, "🍲"),
    GearItem("Pouch", 50, "👝"),
    GearItem("Priest's Pack", 3300, "🎒"),
    GearItem("Quiver", 100, "🏹"),
    GearItem("Ram, Portable", 400, "🐏"),
    GearItem("Ration", 50, "🍞"),
    GearItem("Robe", 100, "👘"),
    GearItem("Rope", 100, "🪢"),
    GearItem("Sack", 1, "🎒"),
    GearItem("Scholar's Pack", 4000, "🎒"),
    GearItem("Shovel", 200, "⛏️"),
    GearItem("Signal Whistle", 5, "📯"),
    GearItem("Spikes, Iron", 100, "⚓", unit_name="spike", value_units=10),
    GearItem("Spyglass", 100000, "🔭"),
    GearItem("String", 10, "🧵"),
    GearItem("Tent", 200, "⛺"),
    GearItem("Tinderbox", 50, "🔥"),
    GearItem("Torch", 1, "🔦"),
    GearItem("Vial", 100, "🧪"),
    GearItem("Waterskin", 20, "💧"),
]
