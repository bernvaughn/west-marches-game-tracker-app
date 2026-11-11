from django.db import transaction
from django.utils import timezone

from ledger.services import Line, record
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
