from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ledger.services import Line, record
from shops.models import ShopStock
from shops.services import AlreadySold, NotStocked, ShopClosed, is_open, sell_price


def buy(character, stock, quantity=1, actor=None, today=None):
    """Buy `quantity` of a stocked item for `character`. All or nothing.

    See the Shops epic design, "Buying". Raises ShopClosed, NotStocked,
    AlreadySold, or ledger InsufficientFunds (which rolls back the decrement).
    """
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
        if stock.quantity is not None:
            updated = ShopStock.objects.filter(pk=stock.pk, quantity__gte=quantity).update(
                quantity=F("quantity") - quantity
            )
            if updated == 0:
                raise AlreadySold()
        price = sell_price(stock) * quantity
        return record(
            character,
            "purchase",
            [Line(coins=-price), Line(item=item, quantity=quantity)],
            note=f"Bought {quantity} × {item} from {shop}",
            actor=actor,
            shop=shop,
        )
