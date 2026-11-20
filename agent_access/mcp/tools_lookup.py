"""Agent tools: look up the club's characters and item catalogue (story A2)."""

from typing import Any

from django.db.models import Prefetch, Q

from items.containers import loot_preview
from items.models import ContainerSlot, ContainerSlotOption, Item
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


def _loot_rows(preview):
    """Convert loot_preview rows to JSON-serialisable dicts.

    Each row: {label, qty_min, qty_max, chance_pct, unknown,
    options:[{label,qty_min,qty_max,weight_pct}]}.
    Masked rows have no item name or id. Never emit item.pk or item.name
    of masked rows.
    """
    rows = []
    for row in preview:
        if row.masked:
            rows.append(
                {
                    "label": "???",
                    "qty_min": None,
                    "qty_max": None,
                    "chance_pct": row.chance_pct,
                    "unknown": True,
                    "options": [],
                }
            )
            continue

        if row.options:
            # "One of" row with weighted options
            options = [
                {
                    "label": opt.label,
                    "qty_min": opt.qty_min,
                    "qty_max": opt.qty_max,
                    "weight_pct": opt.weight_pct,
                }
                for opt in row.options
            ]
            rows.append(
                {
                    "label": row.label,
                    "qty_min": None,
                    "qty_max": None,
                    "chance_pct": row.chance_pct,
                    "unknown": row.unknown,
                    "options": options,
                }
            )
        else:
            # Fixed or ranged single item
            rows.append(
                {
                    "label": row.label,
                    "qty_min": row.qty_min,
                    "qty_max": row.qty_max,
                    "chance_pct": row.chance_pct,
                    "unknown": row.unknown,
                    "options": [],
                }
            )
    return rows


@agent_tool
def search_items(ctx, query: str = "", limit: int = 25) -> dict[str, Any]:
    """Search this club's item catalogue. Retired items are never listed.

    `query` is a case-insensitive match on item name, description or
    traits; an empty query returns all items. `limit` is clamped to 1..100
    (default 25). Each row has `id`, `name`, `description`, `traits`,
    `value_cp`, `value` (formatted coins), `is_container` (bool), and for
    containers `loot` (preview rows from loot_preview with unknowns masked).
    Use the returned `id` in `propose_awards`. If no catalogue item fits the
    loot, call `propose_item` instead of guessing.
    """
    limit = max(1, min(int(limit), 100))
    qs = Item.objects.for_club(ctx.club).filter(retired=False)
    query = (query or "").strip()
    if query:
        qs = qs.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(traits__icontains=query)
        )

    # Prefetch container slots and options for container items to avoid N+1
    qs = qs.prefetch_related(
        Prefetch(
            "slots",
            queryset=ContainerSlot.objects.prefetch_related(
                Prefetch("options", queryset=ContainerSlotOption.objects.select_related("item"))
            ).order_by("position", "id"),
            to_attr="prefetched_slots",
        )
    )

    items_data = []
    for item in qs.order_by("name", "pk")[:limit]:
        item_data = {
            "id": item.pk,
            "name": item.name,
            "description": item.description,
            "traits": item.traits,
            "gm_details": item.gm_details,
            "value_cp": item.value_cp,
            "value": format_coins(item.value_cp),
            "is_container": item.is_container,
        }
        if item.is_container:
            # Build preview with unknowns masked (agents never see real unknowns)
            preview = loot_preview(item, viewer_can_see_unknown=False)
            item_data["loot"] = _loot_rows(preview)
        items_data.append(item_data)

    return {
        "items": items_data,
        "limit": limit,
    }
