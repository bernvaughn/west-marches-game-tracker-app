"""Views for starting equipment magic item requests."""

import json

from django.contrib import messages as flash
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.models import Message
from accounts.permissions import admin_or_gm_required, club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.models import LedgerLine
from ledger.services import record as ledger_record
from player_characters.models import Character
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)


def _get_active_template(club):
    """Return the active starting equipment template for a club."""
    # Use explicit ordering to ensure consistent results
    return (
        StartingEquipmentTemplate.objects.filter(club=club, is_active=True).order_by("name").first()
    )


def _get_magic_options(template):
    """Return MagicItemStartingOption queryset for a template."""
    if template is None:
        return MagicItemStartingOption.objects.none()
    return template.magic_options.select_related("item").order_by("item__name")


@club_member_required
def request_new(request, club_slug, character_pk):
    """
    GET: Render HTMX modal with item picker for magic starting item requests.
    POST: Create PENDING StartingEquipmentRequest + inbox Message (STARTING_REQUEST).
    """
    character = club_get_object_or_404(request, Character, pk=character_pk)

    # Permission check: only owner, admin, or GM can view the sheet and make requests
    membership = request.membership
    can_request = (
        membership.is_club_admin or membership.is_game_master or character.owner_id == membership.id
    )
    if not can_request:
        raise Http404

    template = _get_active_template(request.club)
    magic_options = _get_magic_options(template)

    if request.method == "GET":
        if not magic_options.exists():
            return render_modal_or_page(
                request,
                "starting_equipment/requests/_no_options_modal.html",
                "starting_equipment/requests/no_options.html",
                {"club": request.club, "character": character, "template": template},
            )

        return render_modal_or_page(
            request,
            "starting_equipment/requests/_request_modal.html",
            "starting_equipment/requests/request_modal.html",
            {
                "club": request.club,
                "character": character,
                "magic_options": magic_options,
                "template": template,
            },
        )

    # POST - Create the request
    item_id = request.POST.get("item")
    quantity = request.POST.get("quantity", 1)
    note = request.POST.get("note", "").strip()

    if not item_id:
        return HttpResponseBadRequest("Item is required")

    try:
        item = Item.objects.for_club(request.club).get(pk=item_id)
    except Item.DoesNotExist:
        return HttpResponseBadRequest("Invalid item")

    # Validate item is in the template's magic options
    magic_option = magic_options.filter(item=item).first()
    if not magic_option:
        return HttpResponseBadRequest("Item not available as starting equipment")

    # Validate quantity
    try:
        quantity = int(quantity)
        if quantity < 1 or quantity > magic_option.max_per_character:
            raise ValueError
    except (ValueError, TypeError):
        return HttpResponseBadRequest(
            f"Quantity must be between 1 and {magic_option.max_per_character}"
        )

    # Create the StartingEquipmentRequest
    starting_request = StartingEquipmentRequest.objects.create(
        club=request.club,
        character=character,
        item=item,
        quantity=quantity,
        note=note,
        status=StartingEquipmentRequest.Status.PENDING,
    )

    # Create inbox Message and link it to the request
    body = (
        f"{character.name} requests {quantity}x {item.name} as starting equipment."
        f"{f' Note: {note}' if note else ''}"
    )
    msg = Message.objects.create(
        club=request.club,
        sender=membership,
        character=character,
        body=body,
        kind=Message.Kind.STARTING_REQUEST,
    )
    starting_request.message = msg
    starting_request.save(update_fields=["message"])

    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({"appModalClose": True, "inboxChanged": True})
        return response

    flash.success(request, "Starting equipment request submitted.")
    return redirect("characters:detail", club_slug=club_slug, pk=character.pk)


@club_member_required
@require_GET
def request_status(request, club_slug, pk):
    """
    HTMX partial rendering a single request's status row for character sheet.
    """
    starting_request = club_get_object_or_404(
        request,
        StartingEquipmentRequest,
        pk=pk,
    )
    # Apply select_related after club scoping
    starting_request = StartingEquipmentRequest.objects.select_related("item", "decided_by").get(
        pk=starting_request.pk
    )

    # Check permission: same as character detail view
    character = starting_request.character
    membership = request.membership
    can_view = (
        membership.is_club_admin or membership.is_game_master or character.owner_id == membership.id
    )
    if not can_view:
        raise Http404

    return render(
        request,
        "starting_equipment/requests/_status_row.html",
        {"request": starting_request},
    )


@admin_or_gm_required
@require_POST
def request_decide(request, club_slug, pk, decision):
    """
    Admin/GM approve or decline a starting equipment request.
    """
    starting_request = club_get_object_or_404(
        request,
        StartingEquipmentRequest,
        pk=pk,
    )
    # Apply select_related after club scoping
    starting_request = StartingEquipmentRequest.objects.select_related("character", "item").get(
        pk=starting_request.pk
    )

    if decision not in ("approve", "decline"):
        raise Http404

    if decision == "approve":
        # Set request to APPROVED
        starting_request.status = StartingEquipmentRequest.Status.APPROVED
        starting_request.decided_by = request.user
        starting_request.decided_at = timezone.now()
        starting_request.save(update_fields=["status", "decided_by", "decided_at"])

        # Grant item via ledger - single ledger line for this item only
        ledger_record(
            character=starting_request.character,
            kind="award",
            lines=[
                LedgerLine(
                    item=starting_request.item,
                    quantity=starting_request.quantity,
                    coins=0,
                )
            ],
            note=f"Starting equipment: {starting_request.item.name}",
            actor=request.user,
        )
    else:
        # Decline
        decision_note = request.POST.get("decision_note", "").strip()
        starting_request.status = StartingEquipmentRequest.Status.DECLINED
        starting_request.decided_by = request.user
        starting_request.decided_at = timezone.now()
        starting_request.decision_note = decision_note
        starting_request.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])

    # Mark the linked inbox message handled
    if starting_request.message_id:
        starting_request.message.status = Message.Status.HANDLED
        starting_request.message.save(update_fields=["status"])

    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({"appModalClose": True, "inboxChanged": True})
        return response

    flash.success(request, f"Request {decision}d.")
    return redirect("accounts:message_inbox", club_slug=club_slug)


@admin_or_gm_required
@require_GET
def request_decide_confirm(request, club_slug, pk, decision):
    """
    GET: Render the confirm modal for approving or declining a starting
    equipment request. The confirm form POSTs to request_decide.
    """
    if decision not in ("approve", "decline"):
        raise Http404

    starting_request = club_get_object_or_404(
        request,
        StartingEquipmentRequest,
        pk=pk,
    )

    action = "Approve" if decision == "approve" else "Decline"
    confirm_url = reverse(
        "starting_equipment:request_decide",
        kwargs={"club_slug": club_slug, "pk": pk, "decision": decision},
    )

    return render_modal_or_page(
        request,
        "starting_equipment/requests/_decide_confirm.html",
        "starting_equipment/requests/decide_confirm.html",
        {
            "starting_request": starting_request,
            "decision": decision,
            "action": action,
            "confirm_url": confirm_url,
        },
    )
