"""The character a member is acting as in the current club (U24)."""

from django.core.exceptions import PermissionDenied

from .models import Character, SelectedCharacter

_CACHE = "_selected_character_cache"


def own_characters(request):
    club = getattr(request, "club", None)
    membership = getattr(request, "membership", None)
    if club is None or membership is None:
        return Character.objects.none()
    return Character.objects.for_club(club).filter(owner=membership).not_archived().order_by("name")


def selected_character(request):
    if hasattr(request, _CACHE):
        return getattr(request, _CACHE)
    # Include archived characters in the selection pool so they can be explicitly selected
    owned = list(own_characters(request).filter(archived_at__isnull=False) | own_characters(request))
    # Actually, let's just get all owned characters including archived
    from .models import Character
    club = getattr(request, "club", None)
    membership = getattr(request, "membership", None)
    if club is None or membership is None:
        setattr(request, _CACHE, None)
        return None
    owned = list(
        Character.objects.for_club(club).filter(owner=membership).order_by("name")
    )
    chosen = None
    if len(owned) == 1:
        chosen = owned[0]
    elif owned:
        stored = (
            SelectedCharacter.objects.filter(membership=request.membership)
            .values_list("character_id", flat=True)
            .first()
        )
        chosen = next((c for c in owned if c.pk == stored), None)
        if chosen is None:
            chosen = next((c for c in owned if not c.is_dead), None)
        if chosen is None and owned:
            chosen = owned[0]
    setattr(request, _CACHE, chosen)
    return chosen


def set_selected_character(request, character):
    membership = getattr(request, "membership", None)
    club = getattr(request, "club", None)
    if (
        membership is None
        or club is None
        or character.club_id != club.id
        or character.owner_id != membership.id
    ):
        raise PermissionDenied("That is not your character.")
    SelectedCharacter.objects.update_or_create(
        membership=membership, defaults={"character": character}
    )
    if hasattr(request, _CACHE):
        delattr(request, _CACHE)
