from dataclasses import dataclass

from items.models import Item
from ledger.coins import display_parts
from ledger.services import coin_balance, held_coins, held_items, item_quantities


@dataclass(frozen=True)
class InventoryRow:
    item: Item
    owned: int
    held: int

    @property
    def available(self):
        return self.owned - self.held


@dataclass(frozen=True)
class CoinSummary:
    owned: int
    held: int

    @property
    def available(self):
        return self.owned - self.held

    @property
    def parts(self):
        return list(zip(("pp", "gp", "sp", "cp"), display_parts(self.owned), strict=True))

    @property
    def has_holds(self):
        return self.held > 0


def inventory_rows(character):
    """Owned items (retired included), ordered by item name, with trade holds."""
    owned = {i: q for i, q in item_quantities(character).items() if q > 0}
    if not owned:
        return []
    held = held_items(character)
    items = Item.objects.filter(pk__in=owned).order_by("name", "pk")
    return [InventoryRow(item=i, owned=owned[i.pk], held=held.get(i.pk, 0)) for i in items]


def coin_summary(character):
    return CoinSummary(owned=coin_balance(character), held=held_coins(character))
