from django.shortcuts import render

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404

from ..models import Character

PLACEHOLDER = "player_characters/characters/placeholder.html"


@admin_or_gm_required
def adjust(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    return render(
        request, PLACEHOLDER, {"title": f"Adjust {character.name}", "character": character}
    )


@admin_or_gm_required
def consume(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    return render(
        request, PLACEHOLDER, {"title": f"Consume items: {character.name}", "character": character}
    )
