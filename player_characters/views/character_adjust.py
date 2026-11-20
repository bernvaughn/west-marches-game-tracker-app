from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404
from items.containers import loot_preview
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
from ..forms_adjust import (
    BULK_MAX_ROWS,
    AdjustForm,
    BulkAwardForm,
    ConsumeForm,
    bulk_item_line_formset,
)
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


def _is_int(value):
    """Return True if value can be parsed as an int."""
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _render_bulk_award(request, form, club, items, status=200):
    """Re-render the bulk-award form, keeping checkboxes and posted values."""
    character_data = []
    post = request.POST
    for character in Character.objects.for_club(club).order_by("name", "id"):
        prefix = f"items_{character.pk}"
        # Determine how many rows to show: at least 3, or the posted TOTAL_FORMS (clamped)
        total_forms = 3
        if f"{prefix}-TOTAL_FORMS" in post:
            try:
                total_forms_raw = post.get(f"{prefix}-TOTAL_FORMS", 3) or 3
                total_forms = max(3, min(BULK_MAX_ROWS, int(total_forms_raw)))
            except (TypeError, ValueError):
                total_forms = 3

        item_rows = []
        for i in range(total_forms):
            item_id = post.get(f"{prefix}-{i}-item_id", "")
            item_text = post.get(f"{prefix}-{i}-item", "")
            quantity = post.get(f"{prefix}-{i}-quantity", "")
            value_override = post.get(f"{prefix}-{i}-value_override", "")
            item_rows.append(
                {
                    "index": i,
                    "item_id": item_id,
                    "item": item_text,
                    "quantity": quantity,
                    "value_override": value_override,
                }
            )

        character_data.append(
            {
                "character": character,
                "checked": str(character.pk) in post.getlist("characters"),
                "item_rows": item_rows,
            }
        )
    # Build loot previews for container items (view is admin_or_gm_required, so unmasked)
    loot_previews = {}
    for item in items:
        if item.is_container:
            loot_previews[item.pk] = loot_preview(item, True)
    return render(
        request,
        "player_characters/characters/bulk_award.html",
        {
            "form": form,
            "character_data": character_data,
            "items": items,
            "club": club,
            "loot_previews": loot_previews,
        },
        status=status,
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

        # Build specs for record_many. Per-character input is validated before
        # use: unparseable coins or quantities return a form error and a 400
        # instead of a 500.
        specs = []
        for character in characters:
            # Get per-character coins from POST.
            coins_key = f"coins_{character.pk}"
            coins_raw = request.POST.get(coins_key, "")
            if not coins_raw:
                coins = 0
            elif _is_int(coins_raw):
                coins = int(coins_raw)
            else:
                form.add_error(None, f"Invalid coins amount for {character.name}.")
                return _render_bulk_award(request, form, club, items, status=400)

            lines = []
            if coins:
                lines.append(Line(coins=coins))

            # Get per-character items from POST, validated through the
            # bulk formset (club-scoped item, quantity >= 1, each item once).
            prefix = f"items_{character.pk}"
            if f"{prefix}-TOTAL_FORMS" in request.POST:
                try:
                    total_forms = int(request.POST.get(f"{prefix}-TOTAL_FORMS", 0) or 0)
                except (TypeError, ValueError):
                    total_forms = 0
                # Clamp to avoid runaway loops on malicious input.
                total_forms = max(0, min(BULK_MAX_ROWS, total_forms))
                for i in range(total_forms):
                    qty_key = f"{prefix}-{i}-quantity"
                    qty = request.POST.get(qty_key, "")
                    if qty and not _is_int(qty):
                        form.add_error(None, f"Invalid quantity for {character.name}.")
                        return _render_bulk_award(request, form, club, items, status=400)

                # The template posts the chosen item as a hidden ...-item_id
                # field; map it onto the ...-item field the formset validates.
                formset_data = request.POST.copy()
                for i in range(total_forms):
                    item_id = formset_data.get(f"{prefix}-{i}-item_id", "")
                    if item_id:
                        formset_data[f"{prefix}-{i}-item"] = item_id
                item_formset = bulk_item_line_formset(items, data=formset_data, prefix=prefix)
                if not item_formset.is_valid():
                    formset_messages = list(item_formset.non_form_errors())
                    for formset_form in item_formset.forms:
                        formset_messages.extend(
                            error
                            for field_errors in formset_form.errors.values()
                            for error in field_errors
                        )
                    form.add_error(None, f"{character.name}: " + "; ".join(formset_messages))
                    return _render_bulk_award(request, form, club, items, status=200)
                lines.extend(formset_lines(item_formset, 1))

            if lines:
                specs.append(
                    dict(
                        character=character,
                        kind="award",
                        lines=lines,
                        note=shared_note,
                        date=shared_date,
                        actor=request.user,
                    )
                )

        if not specs:
            form.add_error(
                None, "Enter at least one coin or item amount for at least one character."
            )
            return _render_bulk_award(request, form, club, items, status=200)
        try:
            with transaction.atomic():
                entries = record_many(specs)
        except LedgerError as exc:
            form.add_error(None, str(exc))
            return _render_bulk_award(request, form, club, items, status=200)
        count = len(entries)
        msg = f"Awarded loot to {count} character{'s' if count != 1 else ''}."
        # Add link to award downtime points to the same characters
        char_pks = ",".join(str(c.pk) for c in characters)
        points_url = reverse("downtime:points_award", args=[club_slug]) + f"?characters={char_pks}"
        messages.success(
            request,
            format_html(
                '{} <a href="{}">Award downtime points to these characters</a>', msg, points_url
            ),
        )
        # Redirect to club ledger filtered to the new entries
        ledger_url = reverse("ledger:index", args=[club_slug])
        filter_qs = f"?character={char_pks}&date_from={shared_date}"
        filter_qs += f"&date_to={shared_date}&kind=award"
        return redirect(f"{ledger_url}{filter_qs}")

    return _render_bulk_award(request, form, club, items)
