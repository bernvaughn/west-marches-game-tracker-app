"""View for the starting equipment choices step."""

from django.contrib import messages as flash
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from player_characters.models import Character
from starting_equipment.forms import StartingChoicesForm
from starting_equipment.models import StartingEquipmentTemplate
from starting_equipment.services import (
    AlreadyClaimed,
    explain_starting_equipment,
    get_choice_groups,
)
from starting_equipment.services import (
    claim_starting_equipment as claim_starting_equipment_service,
)

from .claim import _can_claim


@club_member_required
def choices(request, club_slug, character_pk):
    """
    GET/POST: Pick one option per starting equipment choice group.

    Only the character owner, a club admin, or a GM can submit.
    After the player picks, grants the picks plus fixed gear and coins in a
    single 'Starting equipment' ledger entry and redirects to the gear reveal.
    """
    character = club_get_object_or_404(request, Character, pk=character_pk)

    # Permission check: owner, admin, or GM
    if not _can_claim(request, character):
        raise Http404

    # Get active template for club (may be None)
    template = StartingEquipmentTemplate.objects.filter(club=request.club, is_active=True).first()

    groups = get_choice_groups(character, template)

    # Already claimed: nothing to pick, go back to the sheet.
    if character.starting_equipment_claimed:
        flash.error(request, "Starting equipment has already been claimed for this character.")
        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    # No active template or no choice groups: nothing to pick, go to the sheet.
    if not groups:
        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    if request.method == "POST":
        form = StartingChoicesForm(groups, data=request.POST)
        if form.is_valid():
            picks = form.picks()
            try:
                result = claim_starting_equipment_service(
                    character, template, request.user, picks=picks
                )
            except AlreadyClaimed:
                flash.error(
                    request, "Starting equipment has already been claimed for this character."
                )
                return redirect("characters:detail", club_slug=club_slug, pk=character.pk)
            flash.success(request, "Starting equipment claimed.")
            for reason in result.reasons:
                flash.warning(request, reason.message)
            detail_url = reverse(
                "characters:detail",
                kwargs={"club_slug": club_slug, "pk": character.pk},
            )
            reveal_url = f"{detail_url}?starting_equipment=1"
            return redirect(reveal_url)
        # Invalid: re-render with errors (HTTP 200, picks preserved by the bound form).
    else:
        form = StartingChoicesForm(groups)

    reasons = [
        reason
        for reason in explain_starting_equipment(character, template)
        if reason.code != "no_template"
    ]

    group_fields = []
    for index, group in enumerate(groups):
        field = form[f"g_{index}"]
        rows = []
        for subwidget, option in zip(field, group.options, strict=True):
            rows.append(
                {
                    "id_for_label": subwidget.id_for_label,
                    "selected": str(subwidget.data) == str(field.value()),
                    "line_id": option.line_id,
                    "item": option.item,
                    "quantity": option.quantity,
                    "html_name": field.html_name,
                }
            )
        group_fields.append({"group": group, "field": field, "rows": rows})

    return render(
        request,
        "starting_equipment/choices.html",
        {
            "character": character,
            "club": request.club,
            "form": form,
            "groups": groups,
            "group_fields": group_fields,
            "reasons": reasons,
            "sheet_url": reverse(
                "characters:detail", kwargs={"club_slug": club_slug, "pk": character.pk}
            ),
        },
    )
