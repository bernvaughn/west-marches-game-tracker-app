"""Service for seeding pack containers.

Extracted from the seed_pack_containers management command so it can be
called programmatically during default starting equipment seeding.
"""

from collections.abc import Callable
from dataclasses import dataclass

from django.db import transaction

from accounts.models import Club
from items.containers import validate_container_config
from items.models import ContainerSlot, ContainerSlotOption, Item

# Pack definitions: pack name -> list of (content name, qty_min, qty_max, value_cp, symbol)
# Based on 2024 PHB contents. All slots are fixed (chance 100, one option, not unknown).
PACKS = {
    "Diplomat's Pack": [
        ("Chest", 1, 1, 500, "🧰"),
        ("Map or Scroll Case", 2, 2, 100, "📜"),
        ("Fine Clothes", 1, 1, 1500, "👔"),
        ("Ink (1 oz)", 1, 1, 1000, "🖋️"),
        ("Ink Pen", 1, 1, 2, "🖋️"),
        ("Lamp", 1, 1, 50, "🪔"),
        ("Oil (flask)", 2, 2, 10, "🛢️"),
        ("Paper (one sheet)", 5, 5, 20, "📄"),
        ("Perfume (vial)", 1, 1, 500, "🧴"),
        ("Sealing Wax", 1, 1, 50, "🕯️"),
        ("Soap", 1, 1, 2, "🧼"),
    ],
    "Explorer's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Bedroll", 1, 1, 100, "🛌"),
        ("Mess kit", 1, 1, 20, "🍳"),
        ("Tinderbox", 1, 1, 50, "🔥"),
        ("Torch", 10, 10, 1, "🔦"),
        ("Ration", 10, 10, 50, "🍞"),
        ("Waterskin", 1, 1, 20, "💧"),
        ("Hempen rope (50 ft)", 1, 1, 100, "🪢"),
    ],
    "Priest's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Blanket", 1, 1, 50, "🛌"),
        ("Candle", 10, 10, 1, "🕯️"),
        ("Tinderbox", 1, 1, 50, "🔥"),
        ("Alms box", 1, 1, 10, "📦"),
        ("Block of incense", 2, 2, 10, "🕯️"),
        ("Censer", 1, 1, 50, "⚱️"),
        ("Vestments", 1, 1, 500, "👘"),
        ("Ration", 2, 2, 50, "🍞"),
        ("Waterskin", 1, 1, 20, "💧"),
    ],
    "Dungeoneer's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Crowbar", 1, 1, 200, "🔨"),
        ("Hammer", 1, 1, 100, "🔨"),
        ("Piton", 10, 10, 5, "⚓"),
        ("Torch", 10, 10, 1, "🔦"),
        ("Tinderbox", 1, 1, 50, "🔥"),
        ("Ration", 10, 10, 50, "🍞"),
        ("Waterskin", 1, 1, 20, "💧"),
        ("Hempen rope (50 ft)", 1, 1, 100, "🪢"),
    ],
    "Burglar's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Ball bearings (1,000)", 1, 1, 100, "⚪"),
        ("String (10 ft)", 1, 1, 1, "🧵"),
        ("Bell", 1, 1, 10, "🔔"),
        ("Candle", 5, 5, 1, "🕯️"),
        ("Crowbar", 1, 1, 200, "🔨"),
        ("Hammer", 1, 1, 100, "🔨"),
        ("Piton", 10, 10, 5, "⚓"),
        ("Hooded lantern", 1, 1, 500, "🏮"),
        ("Oil (flask)", 2, 2, 100, "🛢️"),
        ("Ration", 5, 5, 50, "🍞"),
        ("Tinderbox", 1, 1, 50, "🔥"),
        ("Waterskin", 1, 1, 20, "💧"),
        ("Hempen rope (50 ft)", 1, 1, 100, "🪢"),
    ],
    "Scholar's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Book", 1, 1, 2500, "📖"),
        ("Ink pen", 1, 1, 20, "🖋️"),
        ("Ink (1 oz)", 1, 1, 100, "🖋️"),
        ("Parchment (10 sheets)", 1, 1, 100, "📜"),
        ("Little bag of sand", 1, 1, 1, "🏖️"),
        ("Small knife", 1, 1, 20, "🔪"),
    ],
    "Entertainer's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Bedroll", 1, 1, 100, "🛌"),
        ("Costume", 2, 2, 500, "🎭"),
        ("Ration", 5, 5, 50, "🍞"),
        ("Waterskin", 1, 1, 20, "💧"),
        ("Instrument (lute)", 1, 1, 3500, "🎵"),
        ("Mirror", 1, 1, 500, "🪞"),
    ],
}


class PackSeedingError(Exception):
    """Raised when pack seeding fails."""


@dataclass
class PackSeedSummary:
    """Summary of a pack seeding operation."""

    configured: int = 0
    skipped_not_in_catalogue: int = 0
    skipped_already_configured: int = 0


def _get_pack_item(club: Club, pack_name: str) -> Item | None:
    """Get pack item by name (case-insensitive), preferring non-retired."""
    return Item.objects.filter(club=club, name__iexact=pack_name).order_by("retired", "pk").first()


def _get_or_create_content_item(
    club: Club, content_name: str, value_cp: int, symbol: str
) -> tuple[Item, bool]:
    """Get or create a content item (case-insensitive match).

    Returns (item, created).
    """
    existing = (
        Item.objects.filter(club=club, name__iexact=content_name).order_by("retired", "pk").first()
    )
    if existing:
        return existing, False

    item = Item.objects.create(
        club=club,
        name=content_name,
        value_cp=value_cp,
        symbol=symbol,
        retired=False,
        is_container=False,
    )
    return item, True


def _noop(_message: str) -> None:
    pass


def _process_pack(
    club: Club, pack_name: str, contents: list[tuple], log: Callable[[str], None]
) -> str:
    """Process a single pack. Returns a status string."""
    pack = _get_pack_item(club, pack_name)
    if not pack:
        log(f"  {pack_name}: not in catalogue, skipping")
        return "not_in_catalogue"

    # A pack with slots is already configured (by an earlier run or an admin).
    if pack.slots.exists():
        log(f"  {pack_name}: already configured, skipping")
        return "already_configured"

    if not pack.is_container:
        pack.is_container = True
        pack.save(update_fields=["is_container"])
        log(f"  {pack_name}: set is_container=True")

    content_items_created = 0
    for position, (content_name, qty_min, qty_max, value_cp, symbol) in enumerate(contents):
        # Skip if content is the pack itself
        if content_name.lower() == pack_name.lower():
            continue

        content_item, created = _get_or_create_content_item(club, content_name, value_cp, symbol)
        if created:
            content_items_created += 1
            log(f"    Created content item: {content_name}")

        slot = ContainerSlot.objects.create(
            container=pack,
            chance_pct=100,
            unknown=False,
            position=position,
        )
        ContainerSlotOption.objects.create(
            slot=slot,
            item=content_item,
            qty_min=qty_min,
            qty_max=qty_max,
            weight=1,
        )

    try:
        validate_container_config(pack)
    except Exception as e:
        raise PackSeedingError(f"Validation failed for {pack_name}: {e}") from e

    log(
        f"  {pack_name}: configured ({len(contents)} slots, "
        f"{content_items_created} new content items)"
    )
    return "configured"


def seed_pack_containers(club: Club, log: Callable[[str], None] | None = None) -> PackSeedSummary:
    """Seed all 5e packs as containers with fixed slots for a club.

    Idempotent: existing packs with slots are skipped.
    Only configures packs already in the club's catalogue.

    Args:
        club: The club to seed packs for.
        log: Optional callback that receives one progress line per step.

    Returns:
        PackSeedSummary with counts of configured/skipped packs.

    Raises:
        PackSeedingError: If validation fails for a pack.
    """
    log = log or _noop
    summary = PackSeedSummary()

    with transaction.atomic():
        for pack_name, contents in PACKS.items():
            result = _process_pack(club, pack_name, contents, log)
            if result == "configured":
                summary.configured += 1
            elif result == "not_in_catalogue":
                summary.skipped_not_in_catalogue += 1
            elif result == "already_configured":
                summary.skipped_already_configured += 1

    return summary
