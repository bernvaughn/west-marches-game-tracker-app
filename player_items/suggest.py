"""Similar-name suggestions for player-written items.

Pure-Python trigram-style similarity over normalized names. Suggests, never chooses.
"""

from items.models import Item
from player_items.models import normalize_name_key


def _trigrams(text: str) -> set[str]:
    """Return the set of character trigrams of padded, normalized text."""
    padded = f"  {text}  "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def _similarity(a: str, b: str) -> float:
    """Trigram-style similarity between two normalized names (0.0 to 1.0)."""
    ta = _trigrams(a)
    tb = _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def suggest_matches(club, name: str) -> list[str]:
    """Return existing Item names in the club resembling ``name``.

    Pure-Python trigram-style similarity over normalized names. Suggests,
    never chooses. Returns up to 5 matches.
    """
    normalized = normalize_name_key(name)
    names = list(Item.objects.for_club(club).values_list("name", flat=True))
    scored = [
        (similarity, existing)
        for existing in names
        if normalize_name_key(existing) != normalized
        and (similarity := _similarity(normalized, normalize_name_key(existing))) > 0
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [existing for _, existing in scored[:5]]
