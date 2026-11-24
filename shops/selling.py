from django.db import transaction
from django.utils import timezone

from items.services import StackedPricingService
from ledger.services import LedgerError, Line, record
from player_characters.life import require_can_sell
from shops.models import ShopStock
from shops.services import ShopClosed, ShopError, is_open, percent_price


def buy_percent_for(shop, item):
    """Buy percent of the item's smallest bundle line, as shops.services.buy_price uses.

    A null override on that line, or no line at all, falls back to the shop default.
    """
    stock = ShopStock.objects.filter(shop=shop, item=item).order_by("bundle_units", "pk").first()
    if stock is not None and stock.buy_percent is not None:
        return stock.buy_percent
    return shop.buy_percent


def sale_total(shop, item, units):
    """What the shop pays for `units` of `item`, computed once from the total units sold.

    Stacked items use sale_price (floor once from the total, no 1 cp minimum).
    Normal items keep percent_price per unit (1 cp minimum), unchanged.
    """
    pct = buy_percent_for(shop, item)
    if item.is_stacked:
        return StackedPricingService.sale_price(item, units, pct)
    return percent_price(item.value_cp, pct) * units


def sell(character, shop, item, quantity=1, actor=None, today=None):
    """Sell `quantity` of an item to a shop at its buy price. Never touches stock."""
    require_can_sell(character)
    today = today or timezone.localdate()
    if quantity < 1:
        raise ShopError("Quantity must be at least 1.")
    if shop.club_id != character.club_id:
        raise ShopError("This shop is not in the character's club.")
    with transaction.atomic():
        if not is_open(shop, today):
            raise ShopClosed()
        price = sale_total(shop, item, quantity)
        if price == 0 and item.is_stacked:
            unit_text = StackedPricingService.unit_label(item, quantity)
            raise ShopError(f"{unit_text} is worth less than 1 cp here. Set it aside instead.")
        lines = [Line(item=item, quantity=-quantity)]
        if price > 0:
            lines.append(Line(coins=price))
        return record(
            character,
            "sale",
            lines,
            note=f"Sold {StackedPricingService.unit_label(item, quantity)} to {shop}",
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

    require_can_sell(character)
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
