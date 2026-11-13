"""Reference items for the item form: same band first, then nearest by value."""

from .models import Item

LIMIT = 10


def reference_items(club, band="", value_cp=0, q="", exclude_pk=None, limit=LIMIT):
    items = Item.objects.for_club(club).filter(retired=False)
    if exclude_pk:
        items = items.exclude(pk=exclude_pk)
    q = (q or "").strip()
    if q:
        return list(items.filter(name__icontains=q).order_by("name")[:limit])
    if not band and not value_cp:
        return []
    pool = sorted(items, key=lambda i: (abs(i.value_cp - value_cp), i.name.lower()))
    same = [i for i in pool if band and i.rarity == band]
    rest = [i for i in pool if not (band and i.rarity == band)]
    return (same + rest)[:limit]
