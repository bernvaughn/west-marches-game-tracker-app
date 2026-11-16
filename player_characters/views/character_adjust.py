from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

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
    record_many,
)

from ..forms import formset_lines, item_line_formset
from ..forms_adjust import AdjustForm, BulkAwardForm, ConsumeForm
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


@admin_or_gm_required
def bulk_award(request, club_slug):
    """Award coins and items to multiple characters at once."""
    club = request.club
    items = Item.objects.for_club(club).filter(retired=False)
    post = request.method == "POST"
    
    form = BulkAwardForm(request.POST if post else None, club=club)
    
    if post and form.is_valid():
        characters = form.cleaned_data["characters"]
        shared_note = form.cleaned_data["note"]
        shared_date = form.cleaned_data["date"]
        
        # Build specs for record_many
        specs = []
        for character in characters:
            # Get per-character coins from POST
            coins_key = f"coins_{character.pk}"
            coins = int(request.POST.get(coins_key, 0) or 0)
            
            # Get per-character items from POST
            lines = []
            if coins:
                lines.append(Line(coins=coins))
            
            # Process item formset for this character
            prefix = f"items_{character.pk}"
            total_forms = int(request.POST.get(f"{prefix}-TOTAL_FORMS", 0) or 0)
            for i in range(total_forms):
                item_key = f"{prefix}-{i}-item"
                qty_key = f"{prefix}-{i}-quantity"
                item_id = request.POST.get(item_key)
                qty = request.POST.get(qty_key)
                if item_id and qty:
                    try:
                        item = items.get(pk=int(item_id))
                        lines.append(Line(item=item, quantity=int(qty)))
                    except (Item.DoesNotExist, ValueError):
                        pass
            
            if lines:
                specs.append(dict(
                    character=character,
                    kind="award",
                    lines=lines,
                    note=shared_note,
                    date=shared_date,
                    actor=request.user,
                ))
        
        if not specs:
            form.add_error(None,
                "Enter at least one coin or item amount for at least one character.")
        else:
            try:
                with transaction.atomic():
                    entries = record_many(specs)
            except LedgerError as exc:
                form.add_error(None, str(exc))
            else:
                count = len(entries)
                msg = f"Awarded loot to {count} character{'s' if count != 1 else ''}."
                messages.success(request, msg)
                # Redirect to club ledger filtered to the new entries
                ledger_url = reverse("ledger:index", args=[club_slug])
                char_pks = ','.join(str(c.pk) for c in characters)
                filter_qs = f"?character={char_pks}&date_from={shared_date}"
                filter_qs += f"&date_to={shared_date}&kind=award"
                return redirect(f"{ledger_url}{filter_qs}")
    
    # For GET or invalid POST, prepare character data for template
    character_data = []
    for character in Character.objects.for_club(club).order_by("name", "id"):
        character_data.append({
            "character": character,
            "checked": str(character.pk) in request.POST.getlist("characters") if post else False,
        })
    
    return render(
        request,
        "player_characters/characters/bulk_award.html",
        {
            "form": form,
            "character_data": character_data,
            "items": items,
            "club": club,
        },
    )
