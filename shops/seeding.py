"""Service for seeding the default General Store.

This module creates a General Store run by Mabel Packwell (a halfling grocer)
stocked with every basic adventuring item from the 2024 PHB Adventuring Gear
table plus ammunition. The shop sells at 100% of base value and buys back at 75%.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from accounts.models import Club
from items.models import Item
from items.rarity import BANDS, Rarity
from shops.gear import GENERAL_STORE_GEAR
from shops.models import Rotation, Shop, ShopStock

# Shop constants
SHOP_NAME = "General Store"
KEEPER_NAME = "Mabel Packwell"
KEEPER_DESCRIPTION = (
    "A cheerful halfling grocer who knows every price by heart "
    "and always has a kind word for adventurers."
)
SHOP_DESCRIPTION = (
    "A well-stocked general store on the main street. "
    "Sells all basic adventuring gear at fair prices."
)
SELL_PERCENT = 100
BUY_PERCENT = 75
COLOR = "parchment"
SILHOUETTE = Shop.Silhouette.HALFLING_GROCER
BUILDING = Shop.Building.GENERAL_STORE
STREET_POSITION = 0
SYMBOL = "🧺"
ROTATION_NAME = "Always open"


@dataclass(frozen=True)
class GeneralStoreSummary:
    """Summary of the General Store seeding operation."""

    shop_created: bool = False
    skipped: bool = False
    items_created: int = 0
    stock_created: int = 0


def _get_rarity_for_value(value_cp: int) -> str:
    """Return the everyday-goods rarity band for a value in copper."""
    for rarity in [
        Rarity.TRIVIAL,
        Rarity.CHEAP,
        Rarity.STANDARD,
        Rarity.FINE,
        Rarity.LUXURY,
        Rarity.EXOTIC,
    ]:
        low, high = BANDS[rarity][0], BANDS[rarity][1]
        if high is None or value_cp <= high:
            if value_cp >= low:
                return rarity
    # Fallback for values above EXOTIC (shouldn't happen for gear)
    return Rarity.EXOTIC


def _get_or_create_gear_item(
    club: Club,
    name: str,
    value_cp: int,
    icon: str,
    unit_name: str | None = None,
    value_units: int = 1,
    description: str = "",
    weight_lb: float | None = None,
) -> tuple[Item | None, bool]:
    """Get or create a gear item by case-insensitive name.

    Returns (item, created). Never overwrites an existing item.
    If the only match is retired, returns (None, False) so the caller can skip it.
    When ``weight_lb`` is given, the new item is born with that weight
    (hundredths of a pound); otherwise its weight is left blank.
    """
    existing = Item.objects.filter(club=club, name__iexact=name).order_by("retired", "pk").first()
    if existing:
        if existing.retired:
            return None, False
        return existing, False

    rarity = _get_rarity_for_value(value_cp)
    weight_hundredths = None if weight_lb is None else round(weight_lb * 100)
    item = Item.objects.create(
        club=club,
        name=name,
        value_cp=value_cp,
        symbol=icon,
        rarity=rarity,
        retired=False,
        is_container=False,
        is_stacked=unit_name is not None,
        unit_name=unit_name or "",
        value_units=value_units if unit_name else 1,
        weight_hundredth_lb=weight_hundredths,
        description=description,
    )
    return item, True


def seed_default_general_store(club: Club) -> GeneralStoreSummary:
    """Seed the default General Store for a club.

    Idempotent: if a shop named "General Store" already exists (case-insensitive),
    it returns skipped=True and writes nothing. The existing shop keeps its fields,
    stock, position and rotations. Never overwrites existing items or stock rows.

    Creates missing items by name (case-insensitive), never overwrites existing items.
    Creates one ShopStock per gear item with unlimited quantity (None) and no price overrides.
    Adds the shop to an "Always open" rotation at street position 0.

    Args:
        club: The club to seed the General Store for.

    Returns:
        GeneralStoreSummary with the results.
    """
    with transaction.atomic():
        # Check if the shop already exists
        existing_shop = Shop.objects.filter(club=club, name__iexact=SHOP_NAME).first()
        if existing_shop:
            # Leave an existing shop exactly as it is: no field, stock or rotation writes.
            return GeneralStoreSummary(skipped=True)

        # Create or get gear items
        items_created = 0
        gear_items_with_bundle = []  # list of (item, bundle_units)
        for gear in GENERAL_STORE_GEAR:
            item, created = _get_or_create_gear_item(
                club,
                gear.name,
                gear.value_cp,
                gear.icon,
                gear.unit_name,
                gear.value_units,
                gear.description,
                weight_lb=gear.weight_lb,
            )
            if item is not None:
                bundle_units = gear.value_units if gear.unit_name else 1
                gear_items_with_bundle.append((item, bundle_units))
                if created:
                    items_created += 1
            # If item is None (retired), skip this stock row

        # Create the shop
        shop = Shop.objects.create(
            club=club,
            name=SHOP_NAME,
            description=SHOP_DESCRIPTION,
            keeper_name=KEEPER_NAME,
            keeper_description=KEEPER_DESCRIPTION,
            sell_percent=SELL_PERCENT,
            buy_percent=BUY_PERCENT,
            color=COLOR,
            silhouette=SILHOUETTE,
            building=BUILDING,
            street_position=STREET_POSITION,
            symbol=SYMBOL,
        )

        # Create stock rows (unlimited quantity, no price overrides)
        # Stacked items get bundle_units = value_units; plain items get bundle_units = 1
        stock_created = 0
        stock_objects = [
            ShopStock(
                shop=shop,
                item=item,
                bundle_units=bundle_units,
                quantity=None,
                sell_percent=None,
                buy_percent=None,
            )
            for item, bundle_units in gear_items_with_bundle
        ]
        if stock_objects:
            ShopStock.objects.bulk_create(stock_objects)
            stock_created = len(stock_objects)

        # Get or create "Always open" rotation and add the shop
        rotation, _ = Rotation.objects.get_or_create(
            club=club,
            name=ROTATION_NAME,
            defaults={"open_date": timezone.localdate(), "close_date": None},
        )
        rotation.shops.add(shop)

        return GeneralStoreSummary(
            shop_created=True,
            skipped=False,
            items_created=items_created,
            stock_created=stock_created,
        )
