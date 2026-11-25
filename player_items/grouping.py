"""Grouping helpers for the player-item review page.

Player items are grouped by their normalized ``name_key``. Since ``name_key`` is
normalised (lowercased, collapsed spaces) on save, grouping by it is already
case- and spacing-insensitive.
"""

from __future__ import annotations

OPEN = "open"


def _canonical_name(name_key: str) -> str:
    """Return a human-friendly display name from a name_key."""
    return name_key.capitalize()


def group_by_name_key(items):
    """Group player items by their normalized ``name_key``.

    Returns a list of group dicts with keys:
    ``name_key``, ``display_name``, ``total_quantity``, ``holder_count``,
    ``first_date``, ``last_date``, ``items`` and ``open_count``.
    """
    groups = {}
    for item in items:
        group = groups.setdefault(
            item.name_key,
            {
                "name_key": item.name_key,
                "display_name": _canonical_name(item.name_key),
                "items": [],
            },
        )
        group["items"].append(item)

    result = []
    for group in groups.values():
        items = group["items"]
        result.append(
            {
                "name_key": group["name_key"],
                "display_name": group["display_name"],
                "total_quantity": sum(item.quantity for item in items),
                "holder_count": len({item.character_id for item in items}),
                "first_date": min(item.created for item in items),
                "last_date": max(item.created for item in items),
                "items": items,
                "open_count": sum(1 for item in items if item.review == OPEN),
            }
        )
    return result
