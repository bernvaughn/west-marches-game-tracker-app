"""Character selector context (Contract): provides quick stats
for each character in the selector dropdown."""

from django.db.models import Sum

from downtime.models import DowntimePointEntry

from .inventory import coin_summary
from .junk import junk_rows, junk_value


def character_selector_context(character):
    """Return a dict of quick stats for a character to show in the selector."""
    # Coins
    coins = coin_summary(character)
    coin_str = ""
    if coins.owned > 0:
        parts = []
        for denom, amount in coins.parts:
            if amount > 0:
                parts.append(f"{amount} {denom}")
        coin_str = " ".join(parts)

    # Junk count
    junk = junk_rows(character)
    junk_total_qty = sum(r.quantity for r in junk)
    junk_val = junk_value(character, junk)

    # Downtime points
    dt_balance = (
        DowntimePointEntry.objects.filter(character=character).aggregate(total=Sum("delta"))[
            "total"
        ]
        or 0
    )

    return {
        "coins": coin_str,
        "junk_qty": junk_total_qty,
        "junk_value": junk_val,
        "downtime": dt_balance,
    }


def all_characters_selector_context(request):
    """Return a list of (character, context) for all owned characters, dead last."""
    from .selection import own_characters

    characters = list(own_characters(request))
    characters.sort(key=lambda c: (c.is_dead, c.name.lower()))
    return [(c, character_selector_context(c)) for c in characters]
