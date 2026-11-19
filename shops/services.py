from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

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


def format_vs_base_text(vs_base_cp):
    """Format the price difference vs base value as 'vs base: -X gp / +Y gp'."""
    gp = vs_base_cp / 100
    if gp == 0:
        return "vs base: 0 gp"
    sign = "+" if gp > 0 else "-"
    return f"vs base: {sign}{abs(gp):g} gp"


def buy_price(shop, item):
    stock = ShopStock.objects.filter(shop=shop, item=item).first()
    if stock is not None and stock.buy_percent is not None:
        percent = stock.buy_percent
    else:
        percent = shop.buy_percent
    return percent_price(item.value_cp, percent)


SHOP_TIEBREAK = (Lower("name"), Lower("keeper_name"), "id")


def ordered_shops(qs):
    """Street order: position, then name, keeper name (case-insensitive), id."""
    return qs.order_by("street_position", *SHOP_TIEBREAK)


def shop_sort_key(shop):
    return (shop.street_position, shop.name.casefold(), shop.keeper_name.casefold(), shop.id)


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


def set_street_order(club, ordered_shop_ids):
    """Reindex street_position for club's shops in the given order.

    Only shops that belong to club are written, so another club's shops
    can never be reordered through this call. Shops missing from the list
    keep their current position.
    """
    shops = {str(shop.pk): shop for shop in club.shops.all()}
    with transaction.atomic():
        position = 0
        for shop_id in ordered_shop_ids:
            shop = shops.get(str(shop_id))
            if shop is None:
                continue
            if shop.street_position != position:
                shop.street_position = position
                shop.save(update_fields=["street_position"])
            position += 1


CLOSING_SOON_DAYS = 3


def leave_dates(shops, today=None):
    """Return {shop.pk: date | None} for when each shop leaves the street.

    A shop leaves on the latest close_date among its open rotations.
    If any open rotation has no close_date, the shop never leaves (None).
    Shops not in any open rotation get None.
    """
    if today is None:
        today = timezone.localdate()
    if not shops:
        return {}
    shop_ids = [s.pk for s in shops]
    # One query on the through model: shop_id, rotation__close_date
    rows = Shop.rotations.through.objects.filter(
        Q(shop_id__in=shop_ids)
        & Q(rotation__open_date__lte=today)
        & (Q(rotation__close_date__isnull=True) | Q(rotation__close_date__gte=today))
    ).values_list("shop_id", "rotation__close_date")
    # Group by shop: any None -> None; else max close_date
    by_shop = defaultdict(list)
    for shop_id, close_date in rows:
        by_shop[shop_id].append(close_date)
    result = {}
    for shop_id in shop_ids:
        dates = by_shop.get(shop_id)
        if not dates:
            result[shop_id] = None
        elif any(d is None for d in dates):
            result[shop_id] = None
        else:
            result[shop_id] = max(dates)
    return result


def leaves_street_on(shop, today=None):
    """Return the date this shop leaves the street, or None."""
    return leave_dates([shop], today).get(shop.pk)


def closing_soon_on(leaves_on, today=None):
    """Return leaves_on when today <= leaves_on <= today + 3 days, else None."""
    if today is None:
        today = timezone.localdate()
    if leaves_on is None:
        return None
    if today <= leaves_on <= today + timedelta(days=CLOSING_SOON_DAYS):
        return leaves_on
    return None


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
