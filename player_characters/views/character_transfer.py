from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.services import LedgerError, Line, available_coins, available_items, record_many

from ..access import owns_character
from ..forms import formset_lines, item_line_formset
from ..forms_transfer import TransferForm
from ..models import Character
from ..selection import own_characters, selected_character

NO_AMOUNT = "Enter at least one coin or item amount."


def _specs(character, dest, lines, note, actor):
    def suffix():
        return f": {note}" if note else ""

    return [
        dict(
            character=character,
            kind="transfer",
            actor=actor,
            lines=lines,
            note=f"Transferred to {dest.name}{suffix()}",
        ),
        dict(
            character=dest,
            kind="transfer",
            actor=actor,
            lines=[Line(item=ln.item, quantity=-ln.quantity, coins=-ln.coins) for ln in lines],
            note=f"Transferred from {character.name}{suffix()}",
        ),
    ]


@club_member_required
def transfer_start(request, club_slug):
    """Entry for moving items: start from the selected (or chosen own) character."""
    owned = own_characters(request)
    raw = request.GET.get("from")
    if raw:
        if not raw.isdigit():
            raise Http404("No such character.")
        character = owned.filter(pk=int(raw)).first()
        if character is None:
            raise Http404("No such character.")
    else:
        character = selected_character(request)
    if character is None:
        return render(request, "player_characters/characters/transfer.html", {"no_character": True})
    return redirect("characters:transfer", club_slug=club_slug, pk=character.pk)


@club_member_required
def transfer(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    if not owns_character(request.user, character):
        raise PermissionDenied
    destinations = (
        Character.objects.for_club(request.club)
        .filter(owner=character.owner)
        .exclude(pk=character.pk)
        .order_by("name")
    )
    context = {
        "character": character,
        "destinations": destinations,
        "sources": own_characters(request),
    }
    if not destinations.exists():
        return render(request, "player_characters/characters/transfer.html", context)

    avail = available_items(character)
    items = Item.objects.for_club(request.club).filter(
        pk__in=[i for i, q in avail.items() if q > 0]
    )
    post = request.method == "POST"
    form = TransferForm(request.POST if post else None, destinations=destinations)
    formset = item_line_formset(items, request.POST if post else None)
    if post and form.is_valid() and formset.is_valid():
        lines = formset_lines(formset, -1)
        coins = form.cleaned_data.get("coins") or 0
        if coins:
            lines.append(Line(coins=-coins))
        if not lines:
            form.add_error(None, NO_AMOUNT)
        else:
            dest = form.cleaned_data["destination"]
            try:
                record_many(_specs(character, dest, lines, form.cleaned_data["note"], request.user))
            except LedgerError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"Moved loot from {character.name} to {dest.name}.")
                return redirect("characters:detail", club_slug=club_slug, pk=character.pk)
    context.update(
        form=form,
        formset=formset,
        coins_available=available_coins(character),
        available=[(item, avail[item.pk]) for item in items.order_by("name")],
    )
    return render(request, "player_characters/characters/transfer.html", context)
