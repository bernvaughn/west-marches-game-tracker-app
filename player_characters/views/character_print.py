from django.shortcuts import render

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..access import require_inventory_access
from ..inventory import coin_summary, inventory_rows
from ..models import Character


@club_member_required
def print_items(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)
    return render(
        request,
        "player_characters/characters/print.html",
        {
            "character": character,
            "rows": inventory_rows(character),
            "coins": coin_summary(character),
        },
    )
