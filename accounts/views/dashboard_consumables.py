"""Consumable quick-consume view for dashboard."""

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.services import available_items
from player_characters.forms_adjust import PlayerConsumeForm
from player_characters.selection import selected_character


@club_member_required
def consumable_consume_partial(request, club_slug, item_pk):
    """HTMX partial endpoint for consumable confirm modal."""
    club = request.club
    character = selected_character(request)

    if character is None:
        raise Http404("No character selected.")

    item = club_get_object_or_404(request, Item, pk=item_pk)

    # Verify character owns this item
    available = available_items(character).get(item.pk, 0)
    if available < 1:
        raise Http404("The character has none of this item available.")

    # Check if item is actually consumable (quantity > 1 or has consumable trait)
    is_consumable = available > 1 or (item.traits and "consumable" in item.traits.lower())
    if not is_consumable:
        raise Http404("This item is not a consumable.")

    # Build form for GET request
    if request.method == "GET":
        form = PlayerConsumeForm(available=available)
        ctx = {
            "character": character,
            "item": item,
            "available": available,
            "form": form,
            "consume_url": reverse(
                "characters:player_consume",
                args=[club.slug, character.pk, item.pk],
            ),
        }
        return render(request, "accounts/modals/_consume_confirm.html", ctx)

    # For non-HTML requests, return 405
    raise Http404("Invalid request method.")


@club_member_required
def dashboard_consumable_consume_partial(request, club_slug, item_pk):
    """HTMX partial endpoint for dashboard consumable consume."""
    return consumable_consume_partial(request, club_slug, item_pk)