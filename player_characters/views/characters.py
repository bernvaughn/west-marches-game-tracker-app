from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from accounts.permissions import club_admin_required, club_member_required
from accounts.scoping import club_get_object_or_404

from ..access import can_edit_character
from ..models import Character

PLACEHOLDER = "player_characters/characters/placeholder.html"


@club_member_required
def index(request, club_slug):
    return render(request, "player_characters/characters/index.html")


@club_member_required
def create(request, club_slug):
    return render(request, PLACEHOLDER, {"title": "New character"})


@club_member_required
def detail(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    return render(request, PLACEHOLDER, {"title": character.name, "character": character})


@club_member_required
def edit(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    if not can_edit_character(request.user, character):
        raise PermissionDenied
    return render(request, PLACEHOLDER, {"title": f"Edit {character.name}", "character": character})


@club_admin_required
def handover(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    return render(
        request, PLACEHOLDER, {"title": f"Hand over {character.name}", "character": character}
    )
