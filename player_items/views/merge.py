"""HTMX modal views for merging/matching player-written item groups.

Club admins select multiple review groups and either merge them into a new
catalogue item or match them to an existing one.
"""

from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.htmx import htmx_or_redirect, render_modal_or_page
from accounts.permissions import club_admin_required

from ..forms import MergeForm
from ..models import PlayerItem
from ..resolve import ResolveError, Target, resolve
from ..suggest import suggest_matches as get_suggestions


@club_admin_required
def merge_form(request, club_slug):
    """GET: render the merge form with selected groups summarized.

    POST: validate the form, build preview data, render merge_preview.html.
    """
    club = request.club
    # Get selected name_keys from POST or GET
    if request.method == "POST":
        name_keys = request.POST.getlist("name_keys")
    else:
        name_keys = request.GET.getlist("name_keys")

    if len(name_keys) < 2:
        return redirect("player_items:review", club_slug=club.slug)

    entries = list(
        PlayerItem.objects.for_club(club)
        .filter(name_key__in=name_keys, review=PlayerItem.Review.OPEN)
        .select_related("character", "character__owner", "character__owner__user")
        .order_by("name_key", "character__name", "created")
    )
    if not entries:
        return redirect("player_items:review", club_slug=club.slug)

    holders = _build_holders(entries)
    groups = _summarize_groups(entries)

    # Build form action URL with all name_keys
    form_action = reverse("player_items:merge_form", args=[club.slug])
    if name_keys:
        form_action += "?" + "&".join(f"name_keys={nk}" for nk in name_keys)

    if request.method == "POST":
        form = MergeForm(request.POST, club=club)
        if form.is_valid():
            preview_data = _build_preview_data(entries, form, club)
            # Store form data in session for confirm step
            request.session["merge_form_data"] = {
                "name_keys": name_keys,
                "mode": form.cleaned_data["mode"],
                "name": form.cleaned_data.get("name", ""),
                "is_stacked": form.cleaned_data.get("is_stacked", False),
                "unit_name": form.cleaned_data.get("unit_name", ""),
                "quantity_factor": form.cleaned_data.get("quantity_factor", 1),
                "item_id": (
                    form.cleaned_data.get("item").pk if form.cleaned_data.get("item") else None
                ),
            }
            ctx = {
                "club": club,
                "groups": groups,
                "holders": preview_data["holders"],
                "mode": form.cleaned_data["mode"],
                "target_name": preview_data["target_name"],
                "target_is_stacked": preview_data["target_is_stacked"],
                "target_unit_name": preview_data["target_unit_name"],
                "quantity_factor": preview_data["quantity_factor"],
                "confirm_url": reverse("player_items:merge_confirm", args=[club.slug]),
                "form_action": form_action,
                "modal_title": "Preview merge",
            }
            return render_modal_or_page(
                request,
                "player_items/merge_preview.html",
                "player_items/merge_preview.html",
                ctx,
            )
    else:
        initial = {"name_keys": name_keys}
        form = MergeForm(initial=initial, club=club)

    ctx = {
        "club": club,
        "groups": groups,
        "holders": holders,
        "form": form,
        "form_action": form_action,
        "modal_title": "Merge player-written items",
    }
    return render_modal_or_page(
        request,
        "player_items/merge.html",
        "player_items/merge.html",
        ctx,
    )


@club_admin_required
def merge_confirm(request, club_slug):
    """POST: execute the merge/match from stored form data."""
    club = request.club
    form_data = request.session.pop("merge_form_data", None)
    if not form_data:
        return htmx_or_redirect(request, reverse("player_items:review", args=[club.slug]))

    name_keys = form_data["name_keys"]
    entries = list(
        PlayerItem.objects.for_club(club)
        .filter(name_key__in=name_keys, review=PlayerItem.Review.OPEN)
        .select_related("character")
        .order_by("name_key", "character__name", "created")
    )
    if not entries:
        return htmx_or_redirect(request, reverse("player_items:review", args=[club.slug]))

    if form_data["item_id"]:
        from items.models import Item

        target = Target(
            item=Item.objects.for_club(club).get(pk=form_data["item_id"]),
            quantity_factor=form_data["quantity_factor"],
        )
    else:
        target = Target(
            name=form_data["name"],
            is_stacked=form_data["is_stacked"],
            unit_name=form_data["unit_name"],
            quantity_factor=form_data["quantity_factor"],
        )

    try:
        resolve(club, entries, target, request.user, mode=form_data["mode"])
    except ResolveError as exc:
        # Re-render form with error - reconstruct form
        form = MergeForm(form_data, club=club)
        form.add_error(None, exc)
        holders = _build_holders(entries)
        groups = _summarize_groups(entries)
        form_action = reverse("player_items:merge_form", args=[club.slug])
        if name_keys:
            form_action += "?" + "&".join(f"name_keys={nk}" for nk in name_keys)
        ctx = {
            "club": club,
            "groups": groups,
            "holders": holders,
            "form": form,
            "form_action": form_action,
            "modal_title": "Merge player-written items",
        }
        return render_modal_or_page(
            request,
            "player_items/merge.html",
            "player_items/merge.html",
            ctx,
        )

    return htmx_or_redirect(request, reverse("player_items:review", args=[club.slug]))


@club_admin_required
def suggest_matches_view(request, club_slug):
    """HTMX endpoint: return suggestion list for a partial name."""
    club = request.club
    name = request.GET.get("name", "").strip()
    if len(name) < 2:
        return render(request, "player_items/_suggestions.html", {"suggestions": []})
    suggestions = get_suggestions(club, name)
    return render(request, "player_items/_suggestions.html", {"suggestions": suggestions})


def _summarize_groups(entries):
    """Summarize entries by name_key for display."""
    groups = {}
    for entry in entries:
        group = groups.setdefault(
            entry.name_key,
            {
                "name_key": entry.name_key,
                "display_name": entry.name,
                "entries": 0,
                "total_quantity": 0,
                "holders": set(),
            },
        )
        group["entries"] += 1
        group["total_quantity"] += entry.quantity
        group["holders"].add(entry.character_id)
    # Convert holders set to count
    for group in groups.values():
        group["holder_count"] = len(group["holders"])
        del group["holders"]
    return list(groups.values())


def _build_holders(entries):
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


def _build_preview_data(entries, form, club):
    """Build per-holder before/after preview data."""
    mode = form.cleaned_data["mode"]
    quantity_factor = form.cleaned_data.get("quantity_factor") or 1

    if mode == "merge":
        target_name = form.cleaned_data["name"]
        target_is_stacked = form.cleaned_data.get("is_stacked", False)
        target_unit_name = form.cleaned_data.get("unit_name", "")
    else:  # match
        target_item = form.cleaned_data["item"]
        target_name = target_item.name
        target_is_stacked = target_item.is_stacked
        target_unit_name = target_item.unit_name

    # For each holder, compute their current total from selected entries
    # and what the new total will be.
    # We need to check if they already have the target item (for match mode).
    holders = _build_holders(entries)

    for holder in holders:
        character = holder["character"]
        current_total = holder["total_quantity"]
        new_quantity = current_total * quantity_factor

        # Current items this character holds from the selected entries
        holder["current_items"] = [
            {"name": e.name, "quantity": e.quantity} for e in holder["entries"]
        ]

        # For match mode, check if character already has this item
        if mode == "match":
            from ledger.services import item_quantities

            held = item_quantities(character)
            item_pk = form.cleaned_data["item"].pk
            existing_qty = held.get(item_pk, 0)
            holder["existing_quantity"] = existing_qty
            holder["new_total_quantity"] = existing_qty + new_quantity
        else:
            holder["existing_quantity"] = 0
            holder["new_total_quantity"] = new_quantity

    return {
        "holders": holders,
        "target_name": target_name,
        "target_is_stacked": target_is_stacked,
        "target_unit_name": target_unit_name,
        "quantity_factor": quantity_factor,
    }
