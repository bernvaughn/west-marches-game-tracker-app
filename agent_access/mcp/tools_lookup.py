"""Agent tools: look up the club's characters and item catalogue (story A2)."""

from typing import Any

from django.db.models import Q

from items.models import Item
from ledger.coins import format_coins
from player_characters.models import Character

from .server import agent_tool


@agent_tool
def list_characters(ctx, search: str = "") -> dict[str, Any]:
    """List the characters of this club, ordered by name.

    Use it to match character names in session notes to character ids.
    `search` is an optional case-insensitive part of the name; an empty
    search returns every character. Only this club's characters are
    returned. Each row has `id`, `name` and `owner_display_name`. Use the
    returned `id` in `propose_awards`.
    """
    qs = Character.objects.for_club(ctx.club).select_related("owner__user")
    search = (search or "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    return {
        "characters": [
            {
                "id": c.pk,
                "name": c.name,
                "owner_display_name": c.owner.user.display_name,
            }
            for c in qs.order_by("name", "pk")
        ]
    }


@agent_tool
def search_items(ctx, query: str = "", limit: int = 25) -> dict[str, Any]:
    """Search this club's item catalogue. Retired items are never listed.

    `query` is a case-insensitive match on item name, description or
    traits; an empty query returns all items. `limit` is clamped to 1..100
    (default 25). Each row has `id`, `name`, `description`, `traits`,
    `value_cp` and `value` (formatted coins). Use the returned `id` in
    `propose_awards`. If no catalogue item fits the loot, call
    `propose_item` instead of guessing.
    """
    limit = max(1, min(int(limit), 100))
    qs = Item.objects.for_club(ctx.club).filter(retired=False)
    query = (query or "").strip()
    if query:
        qs = qs.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(traits__icontains=query)
        )
    return {
        "items": [
            {
                "id": i.pk,
                "name": i.name,
                "description": i.description,
                "traits": i.traits,
                "value_cp": i.value_cp,
                "value": format_coins(i.value_cp),
            }
            for i in qs.order_by("name", "pk")[:limit]
        ],
        "limit": limit,
    }
