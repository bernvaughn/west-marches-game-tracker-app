"""HTMX modal view for promoting a player-written item group.

Club admins promote a group of player-written items (same name_key from the
review page) into a new or existing catalogue Item.
"""

from django.shortcuts import redirect
from django.urls import reverse

from accounts.htmx import htmx_or_redirect, render_modal_or_page
from accounts.permissions import club_admin_required

from ..forms import PromoteForm
from ..models import PlayerItem
from ..resolve import ResolveError, Target, resolve


@club_admin_required
def promote(request, club_slug, name_key):
    """GET: render the promote modal with a per-holder preview.

    POST: validate the form, call :func:`player_items.resolve.resolve`, and on
    success HX-redirect to the review page. On ``ResolveError`` re-render the
    modal with the error.
    """
    club = request.club
    entries = list(
        PlayerItem.objects.for_club(club)
        .filter(name_key=name_key, review=PlayerItem.Review.OPEN)
        .select_related("character", "character__owner", "character__owner__user")
        .order_by("character__name", "created")
    )
    if not entries:
        return redirect("player_items:review", club_slug=club.slug)

    holders = _holders(entries)
    form_action = reverse("player_items:promote", args=[club.slug, name_key])

    if request.method == "POST":
        form = PromoteForm(request.POST)
        if form.is_valid():
            target = Target(
                name=form.cleaned_data["name"],
                is_stacked=bool(form.cleaned_data["is_stacked"]),
                unit_name=form.cleaned_data.get("unit_name") or "",
                quantity_factor=form.cleaned_data.get("quantity_factor") or 1,
            )
            try:
                resolve(club, entries, target, request.user)
            except ResolveError as exc:
                form.add_error(None, exc)
            else:
                return htmx_or_redirect(request, reverse("player_items:review", args=[club.slug]))
    else:
        form = PromoteForm()

    ctx = {
        "club": club,
        "name_key": name_key,
        "form": form,
        "holders": holders,
        "form_action": form_action,
        "modal_title": "Promote player-written items",
    }
    return render_modal_or_page(
        request,
        "player_items/promote_modal.html",
        "player_items/promote_modal.html",
        ctx,
    )


def _holders(entries):
    """Group entries into per-holder preview dicts, in first-seen order."""
    holders = {}
    for entry in entries:
        holder = holders.get(entry.character_id)
        if holder is None:
            holder = {
                "character": entry.character,
                "owner": entry.character.owner,
                "entries": [],
                "total_quantity": 0,
            }
            holders[entry.character_id] = holder
        holder["entries"].append(entry)
        holder["total_quantity"] += entry.quantity
    return list(holders.values())
