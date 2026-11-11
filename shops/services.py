from django.db.models import Q

from shops.models import Shop, ShopStock


def percent_price(value_cp, percent):
    """Round down. A non-zero value costs at least 1 cp."""
    price = value_cp * percent // 100
    if value_cp > 0:
        return max(price, 1)
    return price


def sell_price(stock):
    percent = stock.sell_percent if stock.sell_percent is not None else stock.shop.sell_percent
    return percent_price(stock.item.value_cp, percent)


def buy_price(shop, item):
    stock = ShopStock.objects.filter(shop=shop, item=item).first()
    if stock is not None and stock.buy_percent is not None:
        percent = stock.buy_percent
    else:
        percent = shop.buy_percent
    return percent_price(item.value_cp, percent)


def open_shops(club, today):
    # One filter() call so both conditions match the same rotation row.
    return (
        Shop.objects.for_club(club)
        .filter(
            Q(rotations__open_date__lte=today)
            & (Q(rotations__close_date__isnull=True) | Q(rotations__close_date__gte=today))
        )
        .distinct()
    )


def is_open(shop, today):
    """True when the shop is in a rotation open on `today`. Agrees with `open_shops`."""
    return open_shops(shop.club, today).filter(pk=shop.pk).exists()


class ShopError(Exception):
    default_message = "The shop cannot do that."

    def __init__(self, message=None):
        super().__init__(message or self.default_message)


class ShopClosed(ShopError):
    default_message = "This shop is closed."


class NotStocked(ShopError):
    default_message = "This item is not in stock."


class AlreadySold(ShopError):
    default_message = "Already sold: someone bought the last one."
