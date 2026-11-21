from django.db import transaction
from django.db.models import F
from django.utils import timezone

from items.stacked import unit_label
from ledger.services import Line, record
from player_characters.life import require_can_buy
from shops.models import ShopStock
from shops.services import (
    AlreadySold,
    NotStocked,
    PriceChanged,
    ShopClosed,
    is_open,
    sell_price,
)


def buy(character, stock, quantity=1, actor=None, today=None, expected_price=None):
    """Buy `quantity` bundles of a stocked item for `character`. All or nothing.

    See the Shops epic design, "Buying". Raises ShopClosed, NotStocked,
    AlreadySold, PriceChanged, or ledger InsufficientFunds (which rolls back
    the decrement).

    `expected_price` is the per-bundle price the player was shown. When given,
    the purchase is refused if the current price differs, so a stale page can
    never buy at a price that is no longer valid.
    """
    require_can_buy(character)
    today = today or timezone.localdate()
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    with transaction.atomic():
        # Never trust a stale caller object: re-read inside the write lock.
        stock = ShopStock.objects.select_related("shop", "item").get(pk=stock.pk)
        shop, item = stock.shop, stock.item
        if shop.club_id != character.club_id:
            raise NotStocked()
        if not is_open(shop, today):
            raise ShopClosed()
        if item.retired:
            raise NotStocked()
        if expected_price is not None:
            current_price = sell_price(stock)
            if current_price != expected_price:
                raise PriceChanged(expected=expected_price, current=current_price)
        if stock.quantity is not None:
            updated = ShopStock.objects.filter(pk=stock.pk, quantity__gte=quantity).update(
                quantity=F("quantity") - quantity
            )
            if updated == 0:
                raise AlreadySold()
        price = sell_price(stock) * quantity
        units = quantity * stock.bundle_units
        note = f"Bought {unit_label(item, units)} from {shop}"
        return record(
            character,
            "purchase",
            [Line(coins=-price), Line(item=item, quantity=units)],
            note=note,
            actor=actor,
            shop=shop,
        )
