"""Card data for printed item cards (U90). Takes (item, qty) pairs; loot cards (U92) reuse it."""

from dataclasses import dataclass

from .inventory import USE_CIRCLE_CAP

CARD_CAP = 90
CARDS_PER_SHEET = 9
COPIES = ("type", "item")


@dataclass(frozen=True)
class ItemCard:
    item: object
    qty: int
    use_circles: range
    use_overflow: int


def too_many(pairs, copies):
    """True when "One card per item" would pass the cap. Checked before building.

    A stacked item is one card (its total units held), so it counts as one
    toward the cap regardless of quantity.
    """
    if copies == "type":
        return False
    return sum(1 if item.is_stacked else qty for item, qty in pairs) > CARD_CAP


def build_cards(pairs, copies="type"):
    cards = []
    for item, qty in pairs:
        if item.is_stacked:
            # One card per stacked item, showing the total units held.
            cards.append(ItemCard(item, qty, range(0), 0))
        elif copies == "item":
            cards.extend(ItemCard(item, 1, range(1), 0) for _ in range(qty))
        elif qty > 1:
            cards.append(
                ItemCard(item, qty, range(min(qty, USE_CIRCLE_CAP)), max(qty - USE_CIRCLE_CAP, 0))
            )
        else:
            cards.append(ItemCard(item, qty, range(0), 0))
    return cards


def chunk(cards, size=CARDS_PER_SHEET):
    return [cards[i : i + size] for i in range(0, len(cards), size)]
