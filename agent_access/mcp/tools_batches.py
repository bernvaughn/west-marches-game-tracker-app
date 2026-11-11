"""Agent tools: propose award batches and check their status.

These tools only write proposals. They never touch the ledger.
"""

from datetime import date as date_type
from typing import Any

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from mcp.server.mcpserver import Context
from pydantic import BaseModel, Field

from agent_access.models import ProposedBatch, ProposedItem, ProposedLine
from items.models import Item
from ledger.coins import format_coins
from player_characters.models import Character

from .server import ToolError, agent_tool

MAX_LINES = 200
MAX_KEY = 200
MAX_NOTE = 1000
MAX_SOURCE_NOTES = 20000


class AwardLine(BaseModel):
    character_id: int = Field(description="Id of the character who receives the award.")
    item_id: int | None = Field(None, description="Id of a catalogue item. Use one amount kind.")
    proposed_item_id: int | None = Field(
        None, description="Id of an item you proposed that is not yet approved. One amount kind."
    )
    coins_cp: int | None = Field(
        None, description="Coins in copper pieces, greater than zero. One amount kind."
    )
    quantity: int | None = Field(
        None, description="How many items, greater than zero. Items only. Default 1."
    )
    note: str = Field("", description="Short reason for this line, up to 1000 characters.")
    date: str | None = Field(None, description="ISO date YYYY-MM-DD. Default is the batch date.")


def _parse_date(value, where):
    try:
        return date_type.fromisoformat(value)
    except (TypeError, ValueError):
        raise ToolError(f"{where}: date must be ISO YYYY-MM-DD.") from None


def _review_url(mcp_ctx, club, batch):
    path = reverse("agent_access:batch_detail", kwargs={"club_slug": club.slug, "pk": batch.pk})
    try:
        base = str(mcp_ctx.request_context.request.base_url).rstrip("/")
    except AttributeError:
        return path
    return base + path


def _serialize(batch, mcp_ctx):
    lines = batch.lines.select_related("character", "item", "proposed_item").order_by("pk")
    return {
        "batch_id": batch.pk,
        "status": batch.status,
        "date": batch.date.isoformat(),
        "review_url": _review_url(mcp_ctx, batch.club, batch),
        "lines": [
            {
                "line": n,
                "id": line.pk,
                "character_id": line.character_id,
                "character_name": line.character.name,
                "item_id": line.item_id,
                "item_name": line.item.name if line.item else None,
                "proposed_item_id": line.proposed_item_id,
                "proposed_item_name": line.proposed_item.name if line.proposed_item else None,
                "quantity": line.quantity,
                "coins_cp": line.coins,
                "coins": format_coins(line.coins) if line.coins else "",
                "note": line.note,
                "date": line.date.isoformat() if line.date else None,
            }
            for n, line in enumerate(lines, start=1)
        ],
    }


def _existing(ctx, key):
    return (
        ProposedBatch.objects.for_club(ctx.club)
        .select_related("club")
        .filter(connection=ctx.connection, idempotency_key=key)
        .first()
    )


@agent_tool
def propose_awards(
    ctx,
    mcp_ctx: Context,
    idempotency_key: str,
    lines: list[AwardLine],
    date: str | None = None,
    source_notes: str = "",
) -> dict[str, Any]:
    """Propose a batch of awards. Nothing is applied until a game master confirms it on the site.

    Each line has a character_id and exactly one of item_id, proposed_item_id or coins_cp.
    Amounts must be greater than zero. If you send an idempotency_key you used before on this
    connection, the existing batch comes back unchanged with created false. If any line is
    invalid, the whole batch is rejected.
    """
    key = (idempotency_key or "").strip()
    if not key or len(key) > MAX_KEY:
        raise ToolError(f"idempotency_key is required and at most {MAX_KEY} characters.")
    existing = _existing(ctx, key)
    if existing:
        return _serialize(existing, mcp_ctx) | {"created": False}

    if len(source_notes) > MAX_SOURCE_NOTES:
        raise ToolError(f"source_notes is over {MAX_SOURCE_NOTES} characters.")
    batch_date = _parse_date(date, "Batch") if date is not None else timezone.localdate()
    if not lines:
        raise ToolError("lines must not be empty.")
    if len(lines) > MAX_LINES:
        raise ToolError(f"A batch has at most {MAX_LINES} lines.")

    characters = Character.objects.for_club(ctx.club).in_bulk({ln.character_id for ln in lines})
    items = Item.objects.for_club(ctx.club).in_bulk(
        {ln.item_id for ln in lines if ln.item_id is not None}
    )
    proposed = ProposedItem.objects.for_club(ctx.club).in_bulk(
        {ln.proposed_item_id for ln in lines if ln.proposed_item_id is not None}
    )

    rows = []
    for n, ln in enumerate(lines, start=1):
        where = f"Line {n}"
        kinds = [x is not None for x in (ln.item_id, ln.proposed_item_id, ln.coins_cp)]
        if sum(kinds) != 1:
            raise ToolError(f"{where}: give exactly one of item_id, proposed_item_id or coins_cp.")
        if ln.character_id not in characters:
            raise ToolError(f"{where}: character {ln.character_id} not found.")
        if len(ln.note) > MAX_NOTE:
            raise ToolError(f"{where}: note is over {MAX_NOTE} characters.")
        line_date = _parse_date(ln.date, where) if ln.date is not None else None
        quantity = coins = 0
        if ln.coins_cp is not None:
            if ln.quantity is not None:
                raise ToolError(f"{where}: quantity applies to items only.")
            if ln.coins_cp <= 0:
                raise ToolError(f"{where}: coins_cp must be greater than zero.")
            coins = ln.coins_cp
        else:
            quantity = 1 if ln.quantity is None else ln.quantity
            if quantity <= 0:
                raise ToolError(f"{where}: quantity must be greater than zero.")
            if ln.item_id is not None:
                item = items.get(ln.item_id)
                if item is None:
                    raise ToolError(f"{where}: item {ln.item_id} not found.")
                if item.retired:
                    raise ToolError(f"{where}: item {ln.item_id} is retired.")
            else:
                pitem = proposed.get(ln.proposed_item_id)
                if pitem is None:
                    raise ToolError(f"{where}: proposed item {ln.proposed_item_id} not found.")
                if pitem.status == ProposedItem.Status.REJECTED:
                    raise ToolError(f"{where}: proposed item {ln.proposed_item_id} was rejected.")
        rows.append((ln, quantity, coins, line_date))

    try:
        with transaction.atomic():
            batch = ProposedBatch.objects.create(
                club=ctx.club,
                connection=ctx.connection,
                user=ctx.user,
                date=batch_date,
                idempotency_key=key,
                source_notes=source_notes,
                status=ProposedBatch.Status.PENDING,
            )
            ProposedLine.objects.bulk_create(
                ProposedLine(
                    batch=batch,
                    character_id=ln.character_id,
                    item_id=ln.item_id,
                    proposed_item_id=ln.proposed_item_id,
                    quantity=quantity,
                    coins=coins,
                    note=ln.note,
                    date=line_date,
                )
                for ln, quantity, coins, line_date in rows
            )
    except IntegrityError:
        existing = _existing(ctx, key)
        if existing is None:
            raise
        return _serialize(existing, mcp_ctx) | {"created": False}
    return _serialize(batch, mcp_ctx) | {"created": True}


@agent_tool
def get_batch(ctx, mcp_ctx: Context, batch_id: int) -> dict[str, Any]:
    """Show the status and lines of a proposed batch in this club."""
    batch = (
        ProposedBatch.objects.for_club(ctx.club).select_related("club").filter(pk=batch_id).first()
    )
    if batch is None:
        raise ToolError(f"Batch {batch_id} not found.")
    return _serialize(batch, mcp_ctx) | {
        "confirmed_at": batch.confirmed_at.isoformat() if batch.confirmed_at else None,
        "reversed_at": batch.reversed_at.isoformat() if batch.reversed_at else None,
    }
