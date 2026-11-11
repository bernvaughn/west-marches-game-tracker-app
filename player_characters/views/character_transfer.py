from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..access import owns_character
from ..models import Character


@club_member_required
def transfer(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    if not owns_character(request.user, character):
        raise PermissionDenied
    return render(
        request,
        "player_characters/characters/placeholder.html",
        {"title": f"Move loot from {character.name}", "character": character},
    )
