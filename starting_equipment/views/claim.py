"""View for claiming starting equipment."""

from django.contrib import messages as flash
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from accounts.htmx import hx_response, is_htmx
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from player_characters.models import Character
from starting_equipment.models import StartingEquipmentTemplate
from starting_equipment.services import apply_starting_equipment

_NO_GRANT_FALLBACK = "The template has nothing to grant for this character."


def _respond_without_grant(request, club_slug, character, reasons):
    """Flash the reasons (or a fallback) and refresh/redirect without claiming."""
    if reasons:
        for reason in reasons:
            flash.warning(request, reason.message)
    else:
        flash.warning(request, _NO_GRANT_FALLBACK)

    if is_htmx(request):
        return hx_response(refresh=True)
    return redirect("characters:detail", club_slug=club_slug, pk=character.pk)


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
            flash.error(request, "Starting equipment has already been claimed for this character.")
            return hx_response(refresh=True)
        flash.error(request, "Starting equipment has already been claimed for this character.")

        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    # Get active template for club (may be None)
    template = StartingEquipmentTemplate.objects.filter(club=request.club, is_active=True).first()

    # Apply starting equipment
    result = apply_starting_equipment(character, template, request.user)
    entry = result.entry

    # Nothing granted: flash the reasons and do not mark claimed.
    if entry is None:
        return _respond_without_grant(request, club_slug, character, result.reasons)

    # Mark as claimed
    character.starting_equipment_claimed = True
    character.save(update_fields=["starting_equipment_claimed"])

    flash.success(request, "Starting equipment claimed.")
    # A granted entry can still carry reasons (for example a custom background).
    for reason in result.reasons:
        flash.warning(request, reason.message)

    if is_htmx(request):
        return hx_response(refresh=True)

    return redirect("characters:detail", club_slug=club_slug, pk=character.pk)
