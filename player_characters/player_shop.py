"""Player shops (U66): a character lists junk for other players to buy at base value."""

from dataclasses import dataclass

from django.db import transaction

from ledger.services import Line, held_items, item_quantities, record_many

from . import junk
from .models import Character


class PlayerShopError(Exception):
    pass


@dataclass(frozen=True)
class ListedRow:
    item: object
    quantity: int
    price: int


def listed_rows(character):
    """Junk the shop offers: min(junk quantity, owned - held). Empty when closed."""
    if not character.shop_open:
        return []
    held = held_items(character)
    owned = item_quantities(character)
    rows = []
    for row in junk.junk_rows(character):
        available = owned.get(row.item.pk, 0) - held.get(row.item.pk, 0)
        quantity = min(row.quantity, available)
        if quantity > 0:
            rows.append(ListedRow(item=row.item, quantity=quantity, price=row.item.value_cp))
    return rows


def has_listing(character):
    return bool(listed_rows(character))


def listed_quantity(character):
    return sum(r.quantity for r in listed_rows(character))


def buy_from(buyer, seller, item, quantity, actor=None):
    """Buy `quantity` of `item` from the seller's shop at base value. All or nothing.

    Raises PlayerShopError, or ledger InsufficientFunds.
    """
    if quantity < 1:
        raise PlayerShopError("Enter a quantity of 1 or more.")
    with transaction.atomic():
        seller = Character.objects.select_related("owner").get(pk=seller.pk)
        if buyer.club_id != seller.club_id or item.club_id != seller.club_id:
            raise PlayerShopError("This shop is not in your club.")
        if buyer.owner_id == seller.owner_id:
            raise PlayerShopError("This is your shop.")
        if not seller.shop_open:
            raise PlayerShopError("This shop is closed.")
        listed = next((r.quantity for r in listed_rows(seller) if r.item.pk == item.pk), 0)
        if quantity > listed:
            raise PlayerShopError(
                f"Already sold: only {listed} listed." if listed else "Not listed any more."
            )
        price = item.value_cp * quantity
        entries = record_many(
            [
                dict(
                    character=buyer,
                    kind="player_shop",
                    lines=[Line(coins=-price), Line(item=item, quantity=quantity)],
                    note=f"Bought {quantity} × {item} from {seller}'s shop",
                    actor=actor,
                ),
                dict(
                    character=seller,
                    kind="player_shop",
                    lines=[Line(coins=price), Line(item=item, quantity=-quantity)],
                    note=f"Sold {quantity} × {item} to {buyer} from shop",
                    actor=actor,
                ),
            ]
        )
        junk.reduce_junk(seller, {item: quantity})
        return entries[0]
