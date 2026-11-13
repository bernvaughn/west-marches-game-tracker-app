from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.services import (
    LedgerError,
    Line,
    available_coins,
    available_items,
    recent_changes,
    record,
)

from ..forms import formset_lines, item_line_formset
from ..forms_adjust import AdjustForm, ConsumeForm
from ..models import Character

NO_AMOUNT = "Enter at least one coin or item amount."


def _handle(request, character, form, formset, sign, kind):
    """Validate and record. Return True when an entry was written."""
    if not (form.is_valid() and formset.is_valid()):
        return False
    lines = formset_lines(formset, sign)
    coins = form.cleaned_data.get("coins") or 0
    if coins:
        lines.append(Line(coins=sign * coins))
    if not lines:
        form.add_error(None, NO_AMOUNT)
        return False
    try:
        record(
            character,
            kind,
            lines,
            note=form.cleaned_data["note"],
            date=form.cleaned_data["date"],
            actor=request.user,
        )
    except LedgerError as exc:
        form.add_error(None, str(exc))
        return False
    return True


@admin_or_gm_required
def adjust(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    items = Item.objects.for_club(request.club).filter(retired=False)
    post = request.method == "POST"
    form = AdjustForm(request.POST if post else None)
    formset = item_line_formset(items, request.POST if post else None)
    if post:
        valid = form.is_valid() and formset.is_valid()
        sign = form.cleaned_data.get("sign") if valid else None
        if valid and _handle(request, character, form, formset, sign, form.cleaned_data["kind"]):
            messages.success(request, f"Updated {character.name}.")
            return redirect("characters:detail", club_slug=club_slug, pk=character.pk)
    return render(
        request,
        "player_characters/characters/adjust.html",
        {
            "character": character,
            "form": form,
            "formset": formset,
            "recent": recent_changes(character),
        },
    )


@admin_or_gm_required
def consume(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    avail = available_items(character)
    items = Item.objects.for_club(request.club).filter(
        pk__in=[i for i, q in avail.items() if q > 0]
    )
    post = request.method == "POST"
    form = ConsumeForm(request.POST if post else None)
    formset = item_line_formset(items, request.POST if post else None)
    if post and _handle(request, character, form, formset, -1, "consumed"):
        messages.success(request, f"Consumed from {character.name}.")
        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)
    return render(
        request,
        "player_characters/characters/consume.html",
        {
            "character": character,
            "form": form,
            "formset": formset,
            "recent": recent_changes(character),
            "coins_available": available_coins(character),
            "available": [(item, avail[item.pk]) for item in items.order_by("name")],
        },
    )
