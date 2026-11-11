"""Agent tools: propose new catalogue items.

A proposal never creates an items.Item. A game master or club admin must approve it first.
"""

from typing import Any

from django.db import transaction
from django.urls import reverse
from mcp.server.mcpserver import Context

from agent_access.models import ProposedItem
from items.models import Item
from ledger.coins import format_coins

from .server import ToolError, agent_tool

MAX_NAME = 200
MAX_TEXT = 5000
STATUSES = {"pending", "approved", "rejected"}


def _review_url(mcp_ctx, club, proposal):
    path = reverse(
        "agent_access:proposed_item_detail", kwargs={"club_slug": club.slug, "pk": proposal.pk}
    )
    try:
        base = str(mcp_ctx.request_context.request.base_url).rstrip("/")
    except AttributeError:
        return path
    return base + path


def _serialize(p, mcp_ctx):
    return {
        "proposed_item_id": p.pk,
        "name": p.name,
        "description": p.description,
        "traits": p.traits,
        "details": p.details,
        "value_cp": p.value_cp,
        "value": format_coins(p.value_cp) if p.value_cp else "",
        "status": p.status,
        "approved_item_id": p.approved_item_id,
        "review_url": _review_url(mcp_ctx, p.club, p),
    }


@agent_tool
def propose_item(
    ctx,
    mcp_ctx: Context,
    name: str,
    description: str = "",
    traits: str = "",
    details: str = "",
    value_cp: int = 0,
) -> dict[str, Any]:
    """Propose a new catalogue item. It is not usable until a game master approves it.

    Refused if an active item already has this name. If you already proposed this name and it
    is still pending, that proposal is returned with created false.
    """
    name = (name or "").strip()
    if not name:
        raise ToolError("name is required.")
    if len(name) > MAX_NAME:
        raise ToolError(f"name must be at most {MAX_NAME} characters.")
    for label, text in (("description", description), ("traits", traits), ("details", details)):
        if len(text or "") > MAX_TEXT:
            raise ToolError(f"{label} must be at most {MAX_TEXT} characters.")
    if isinstance(value_cp, bool) or not isinstance(value_cp, int) or value_cp < 0:
        raise ToolError("value_cp must be a whole number of copper pieces, 0 or more.")

    with transaction.atomic():
        existing = Item.objects.for_club(ctx.club).filter(retired=False, name__iexact=name).first()
        if existing:
            raise ToolError(
                f"An active catalogue item named '{existing.name}' already exists "
                f"(item_id {existing.pk}). Use that item."
            )
        pending = (
            ProposedItem.objects.for_club(ctx.club)
            .filter(status=ProposedItem.Status.PENDING, name__iexact=name)
            .order_by("pk")
            .first()
        )
        if pending:
            return _serialize(pending, mcp_ctx) | {"created": False}
        proposal = ProposedItem.objects.create(
            club=ctx.club,
            connection=ctx.connection,
            name=name,
            description=description or "",
            traits=traits or "",
            details=details or "",
            value_cp=value_cp,
        )
    return _serialize(proposal, mcp_ctx) | {"created": True}


@agent_tool
def list_proposed_items(ctx, mcp_ctx: Context, status: str = "pending") -> dict[str, Any]:
    """List item proposals for this club. Status is pending, approved, rejected or all.

    Nothing here is usable until a game master approves it.
    """
    if status != "all" and status not in STATUSES:
        raise ToolError("status must be pending, approved, rejected or all.")
    qs = ProposedItem.objects.for_club(ctx.club)
    if status != "all":
        qs = qs.filter(status=status)
    return {
        "status": status,
        "proposed_items": [_serialize(p, mcp_ctx) for p in qs.order_by("-created", "-pk")],
    }
