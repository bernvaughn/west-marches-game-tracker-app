from django.shortcuts import render

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from player_characters.access import require_inventory_access
from player_characters.models import Character


@club_member_required
def index(request, club_slug):
    return render(request, "ledger/index.html")


@club_member_required
def character_history(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)
    return render(
        request,
        "player_characters/characters/placeholder.html",
        {"title": f"History of {character.name}", "character": character},
    )
