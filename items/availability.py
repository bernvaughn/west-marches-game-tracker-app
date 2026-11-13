"""Where to buy (U75): open club shops and open player stalls that offer an item."""

from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Q, Sum
from django.urls import reverse

from ledger.models import LedgerLine
from ledger.services import OPEN_TRADE_STATUSES
from player_characters.models import JunkMark, TradeLine
from shops.models import ShopStock
from shops.services import open_shops, sell_price, shop_sort_key


@dataclass(frozen=True)
class ShopOffer:
    shop: object
    price: int
    quantity: int | None  # None = unlimited
    url: str


@dataclass(frozen=True)
class StallOffer:
    character: object
    price: int
    quantity: int
    url: str
    is_own: bool


@dataclass(frozen=True)
class WhereToBuy:
    shops: list = field(default_factory=list)
    stalls: list = field(default_factory=list)

    def __bool__(self):
        return bool(self.shops or self.stalls)


def _open_stock(club, today):
    return (
        ShopStock.objects.filter(shop__in=open_shops(club, today), item__retired=False)
        .exclude(quantity=0)
        .select_related("shop", "item")
    )


def _stall_quantities(club, item=None):
    """{(character_id, item_id): quantity} listed by open stalls.

    Bulk form of player_characters.player_shop.listed_rows:
    min(junk mark, owned, owned - held in open trades), kept when positive. A fixed
    number of queries however many characters there are.
    """
    marks = JunkMark.objects.filter(
        character__club=club, character__shop_open=True, item__retired=False
    ).select_related("character__owner", "item")
    if item is not None:
        marks = marks.filter(item=item)
    marks = list(marks)
    if not marks:
        return {}, {}
    char_ids = {m.character_id for m in marks}
    item_ids = {m.item_id for m in marks}
    owned = {
        (r["entry__character_id"], r["item_id"]): r["t"]
        for r in LedgerLine.objects.filter(entry__character_id__in=char_ids, item_id__in=item_ids)
        .values("entry__character_id", "item_id")
        .annotate(t=Sum("quantity"))
    }
    held = defaultdict(int)
    open_lines = TradeLine.objects.filter(
        trade__status__in=OPEN_TRADE_STATUSES, item_id__in=item_ids
    ).filter(
        Q(from_sender=True, trade__sender_id__in=char_ids)
        | Q(from_sender=False, trade__receiver_id__in=char_ids)
    )
    for line in open_lines.values(
        "item_id", "from_sender", "trade__sender_id", "trade__receiver_id", "quantity"
    ):
        cid = line["trade__sender_id"] if line["from_sender"] else line["trade__receiver_id"]
        held[(cid, line["item_id"])] += line["quantity"]
    result, chars = {}, {}
    for m in marks:
        key = (m.character_id, m.item_id)
        have = owned.get(key, 0)
        quantity = min(m.quantity, max(have, 0), have - held.get(key, 0))
        if quantity > 0:
            result[key] = quantity
            chars[m.character_id] = m.character
    return result, chars


def available_item_ids(club, today):
    ids = set(_open_stock(club, today).values_list("item_id", flat=True))
    quantities, _ = _stall_quantities(club)
    return ids | {item_id for _, item_id in quantities}


def where_to_buy(club, item, today, viewer):
    if item.retired or item.club_id != club.pk:
        return WhereToBuy()
    stocks = [s for s in _open_stock(club, today).filter(item=item)]
    stocks.sort(key=lambda s: shop_sort_key(s.shop))
    shops = [
        ShopOffer(
            shop=s.shop,
            price=sell_price(s),
            quantity=s.quantity,
            url=reverse("shops:detail", args=[club.slug, s.shop_id]),
        )
        for s in stocks
    ]
    quantities, chars = _stall_quantities(club, item)
    stalls = [
        StallOffer(
            character=c,
            price=item.value_cp,
            quantity=quantities[(cid, item.pk)],
            url=reverse("shops:player_shop", args=[club.slug, cid]),
            is_own=viewer is not None and c.owner.user_id == viewer.pk,
        )
        for cid, c in chars.items()
    ]
    stalls.sort(key=lambda s: (s.character.name.casefold(), s.character.pk))
    return WhereToBuy(shops=shops, stalls=stalls)
