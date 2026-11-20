"""View for the starting gear reveal.

Shows the saved 'Starting equipment' ledger entry: the granted items one by
one, then the starting coins. Read-only: no roll, no write, no service call
that writes. After the reveal the player goes to the character sheet.
"""

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from ledger.models import LedgerEntry
from player_characters.access import require_inventory_access
from player_characters.models import Character


@club_member_required
@require_GET
def character_starting_reveal(request, club_slug, pk):
    """Render the starting gear reveal for ``character``.

    The character owner, a game master or a club admin may view. Other players
    get 403; members of other clubs get 404 via club scoping; anonymous users
    are redirected to login by ``club_member_required``.
    """
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)

    entry = (
        LedgerEntry.objects.filter(
            character=character, kind=LedgerEntry.Kind.AWARD, note="Starting equipment"
        )
        .prefetch_related("lines__item")
        .order_by("id")
        .first()
    )

    # No saved grant: nothing to reveal, send the player to the sheet.
    if entry is None:
        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    # Merge positive-quantity lines per item, ordered by id (same shape as
    # items.opening.opening_view_model).
    rows = []
    for line in entry.lines.filter(quantity__gt=0).select_related("item").order_by("id"):
        row = next((row for row in rows if row["item_id"] == line.item_id), None)
        if row is None:
            rows.append({"item": line.item, "item_id": line.item_id, "qty": line.quantity})
        else:
            row["qty"] += line.quantity

    # Sum the coins over every line (the coin line has item=None).
    coins_cp = sum((line.coins for line in entry.lines.all()), 0)

    sheet_url = reverse("characters:detail", kwargs={"club_slug": club_slug, "pk": character.pk})

    return render(
        request,
        "player_characters/characters/starting_reveal.html",
        {
            "character": character,
            "club": request.club,
            "rows": rows,
            "coins_cp": coins_cp,
            "sheet_url": sheet_url,
        },
    )
