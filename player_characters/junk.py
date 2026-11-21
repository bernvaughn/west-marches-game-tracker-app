"""Junk marks (U47): items a character set aside to sell in one go."""

from dataclasses import dataclass

from items.stacked import sale_price as stacked_sale_price
from items.stacked import unit_label
from ledger.services import item_quantities
from shops.selling import sale_total

from .access import require_inventory_access
from .life import require_can_sell
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


def _base_value(item, qty):
    """Value of `qty` units of `item` at full price (buy percent 100)."""
    if item.is_stacked:
        return stacked_sale_price(item, qty, 100)
    return item.value_cp * qty


def junk_value(character, rows=None):
    rows = junk_rows(character) if rows is None else rows
    return sum(_base_value(r.item, r.quantity) for r in rows)


def junk_value_at(character, shop, rows=None):
    """Total this shop pays for the junk, using its buy percentages."""
    rows = junk_rows(character) if rows is None else rows
    if not rows:
        return 0
    return sum(sale_total(shop, r.item, r.quantity) for r in rows)


def set_junk(character, item, quantity, actor):
    """Mark, change or (quantity 0) unmark junk. Owner, GM or club admin only."""
    require_inventory_access(actor, character)
    require_can_sell(character)
    if item.club_id != character.club_id:
        raise JunkError("This item is not in the character's club.")
    if quantity < 0:
        raise JunkError("Junk quantity cannot be negative.")
    owned = item_quantities(character).get(item.pk, 0)
    if quantity > owned:
        if owned < 1:
            raise JunkError(f"{character} owns no {item.name}.")
        raise JunkError(f"{character} owns only {unit_label(item, owned)}.")
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
