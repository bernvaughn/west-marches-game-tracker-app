"""View for claiming starting equipment."""

import json

from django.contrib import messages as flash
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from player_characters.models import Character
from starting_equipment.models import StartingEquipmentTemplate
from starting_equipment.services import apply_starting_equipment


@club_member_required
@require_POST
def claim_starting_equipment(request, club_slug, character_pk):
    """
    POST: Claim starting equipment for a character.

    Only the character owner, a club admin, or a GM can claim.
    Can only be claimed once per character.
    """
    character = club_get_object_or_404(request, Character, pk=character_pk)

    # Permission check: owner, admin, or GM
    membership = request.membership
    can_claim = (
        membership.is_club_admin or membership.is_game_master or character.owner_id == membership.id
    )
    if not can_claim:
        raise Http404

    # Check if already claimed
    if character.starting_equipment_claimed:
        if is_htmx(request):
            response = HttpResponse(status=400)
            response["HX-Trigger"] = json.dumps(
                {
                    "appModalClose": True,
                    "characterSheetRefresh": True,
                    "claimError": "Already claimed",
                }
            )
            return response
        flash.error(request, "Starting equipment has already been claimed for this character.")

        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    # Get active template for club
    template = StartingEquipmentTemplate.objects.filter(club=request.club, is_active=True).first()

    if template is None:
        if is_htmx(request):
            response = HttpResponse(status=400)
            response["HX-Trigger"] = json.dumps(
                {
                    "appModalClose": True,
                    "characterSheetRefresh": True,
                    "claimError": "No active starting equipment template",
                }
            )
            return response
        flash.error(request, "No active starting equipment template found for this club.")

        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    # Apply starting equipment
    apply_starting_equipment(character, template, request.user)

    # Mark as claimed (even if nothing was granted, to prevent retry loops)
    character.starting_equipment_claimed = True
    character.save(update_fields=["starting_equipment_claimed"])

    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({"appModalClose": True, "characterSheetRefresh": True})
        return response

    flash.success(request, "Starting equipment claimed.")

    return redirect("characters:detail", club_slug=club_slug, pk=character.pk)
