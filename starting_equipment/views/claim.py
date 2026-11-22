"""View for claiming starting equipment."""

from django.contrib import messages as flash
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.htmx import hx_response, is_htmx
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from player_characters import life
from player_characters.models import Character
from starting_equipment.models import StartingEquipmentTemplate
from starting_equipment.services import (
    AlreadyClaimed,
    CharacterCannotClaim,
    get_choice_groups,
)
from starting_equipment.services import (
    claim_starting_equipment as claim_starting_equipment_service,
)

_NO_GRANT_FALLBACK = "The template has nothing to grant for this character."


def _can_claim(request, character):
    """True if the request's user may claim starting equipment for the character."""
    membership = request.membership
    if membership is None:
        return False
    return (
        membership.is_club_admin or membership.is_game_master or character.owner_id == membership.id
    )


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
    if not _can_claim(request, character):
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

    # A dead or archived character cannot claim starting equipment.
    if not life.can_act(character):
        flash.error(request, life.act_block_reason(character))
        if is_htmx(request):
            return hx_response(refresh=True)
        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    # Choice groups must be picked before anything is granted.
    groups = get_choice_groups(character, template)
    if groups:
        choices_url = reverse(
            "starting_equipment:choices",
            kwargs={"club_slug": club_slug, "character_pk": character.pk},
        )
        if is_htmx(request):
            return hx_response(redirect=choices_url)
        return redirect(choices_url)

    # No choice groups: grant via the locked service (one entry, no double grant).
    try:
        result = claim_starting_equipment_service(character, template, request.user)
    except CharacterCannotClaim as exc:
        flash.error(request, str(exc))
        if is_htmx(request):
            return hx_response(refresh=True)
        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)
    except AlreadyClaimed:
        flash.error(request, "Starting equipment has already been claimed for this character.")
        if is_htmx(request):
            return hx_response(refresh=True)
        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    entry = result.entry

    # Nothing granted: flash the reasons and do not mark claimed.
    if entry is None:
        return _respond_without_grant(request, club_slug, character, result.reasons)

    flash.success(request, "Starting equipment claimed.")
    # A granted entry can still carry reasons (for example a custom background).
    for reason in result.reasons:
        flash.warning(request, reason.message)

    if is_htmx(request):
        return hx_response(refresh=True)

    return redirect("characters:detail", club_slug=club_slug, pk=character.pk)
