from django.db import transaction
from django.utils import timezone

from ledger.services import LedgerError, Line, record
from shops.services import ShopClosed, ShopError, buy_price, is_open


def sell(character, shop, item, quantity=1, actor=None, today=None):
    """Sell `quantity` of an item to a shop at its buy price. Never touches stock."""
    today = today or timezone.localdate()
    if quantity < 1:
        raise ShopError("Quantity must be at least 1.")
    if shop.club_id != character.club_id:
        raise ShopError("This shop is not in the character's club.")
    with transaction.atomic():
        if not is_open(shop, today):
            raise ShopClosed()
        price = buy_price(shop, item) * quantity
        lines = [Line(item=item, quantity=-quantity)]
        if price > 0:
            lines.append(Line(coins=price))
        return record(
            character,
            "sale",
            lines,
            note=f"Sold {quantity} × {item} to {shop}",
            actor=actor,
            shop=shop,
        )


class SellLineError(ShopError):
    """One line of a bulk sale failed. `item` names it."""

    def __init__(self, item, message):
        super().__init__(message)
        self.item = item


def sell_many(character, shop, lines, actor=None, today=None):
    """Sell several (item, quantity) lines in one transaction: all or nothing.

    Sold quantities are then taken off the character's junk marks.
    """
    from player_characters.junk import reduce_junk

    if not lines:
        raise ShopError("Tick at least one item.")
    entries = []
    with transaction.atomic():
        for item, quantity in lines:
            try:
                if item.club_id != character.club_id:
                    raise ShopError("This item is not in the character's club.")
                entries.append(sell(character, shop, item, quantity, actor=actor, today=today))
            except (LedgerError, ShopError) as exc:
                raise SellLineError(item, f"{item}: {exc}") from exc
        reduce_junk(character, {item: quantity for item, quantity in lines})
    return entries
