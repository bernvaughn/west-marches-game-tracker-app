"""Junk marks (U47): items a character set aside to sell in one go."""

from dataclasses import dataclass

from ledger.services import item_quantities
from shops.services import percent_price

from .access import require_inventory_access
from .models import JunkMark


class JunkError(Exception):
    pass


@dataclass(frozen=True)
class JunkRow:
    item: object
    quantity: int
    owned: int


def junk_rows(character):
    """Marked items with quantity capped at the number owned. Zero rows are left out."""
    marks = list(JunkMark.objects.filter(character=character).select_related("item"))
    if not marks:
        return []
    owned = item_quantities(character)
    rows = []
    for mark in marks:
        have = max(owned.get(mark.item_id, 0), 0)
        quantity = min(mark.quantity, have)
        if quantity > 0:
            rows.append(JunkRow(item=mark.item, quantity=quantity, owned=have))
    rows.sort(key=lambda r: (r.item.name, r.item.pk))
    return rows


def junk_value(character, rows=None):
    rows = junk_rows(character) if rows is None else rows
    return sum(r.item.value_cp * r.quantity for r in rows)


def junk_value_at(character, shop, rows=None):
    """Total this shop pays for the junk, using its buy percentages."""
    from shops.models import ShopStock

    rows = junk_rows(character) if rows is None else rows
    if not rows:
        return 0
    overrides = dict(
        ShopStock.objects.filter(
            shop=shop, item__in=[r.item for r in rows], buy_percent__isnull=False
        ).values_list("item_id", "buy_percent")
    )
    return sum(
        percent_price(r.item.value_cp, overrides.get(r.item.pk, shop.buy_percent)) * r.quantity
        for r in rows
    )


def set_junk(character, item, quantity, actor):
    """Mark, change or (quantity 0) unmark junk. Owner, GM or club admin only."""
    require_inventory_access(actor, character)
    if item.club_id != character.club_id:
        raise JunkError("This item is not in the character's club.")
    if quantity < 0:
        raise JunkError("Junk quantity cannot be negative.")
    owned = item_quantities(character).get(item.pk, 0)
    if quantity > owned:
        raise JunkError(f"{character} owns only {max(owned, 0)} of {item}.")
    if quantity == 0:
        JunkMark.objects.filter(character=character, item=item).delete()
        return None
    mark, _ = JunkMark.objects.update_or_create(
        character=character, item=item, defaults={"quantity": quantity}
    )
    return mark


def reduce_junk(character, sold):
    """Lower marks by the sold quantities. `sold` maps item to quantity."""
    for item, quantity in sold.items():
        mark = JunkMark.objects.filter(character=character, item=item).first()
        if mark is None:
            continue
        left = mark.quantity - quantity
        if left > 0:
            mark.quantity = left
            mark.save(update_fields=["quantity"])
        else:
            mark.delete()
