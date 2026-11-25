"""Admin review page for player-written items.

Groups player items by ``name_key`` and lets club admins review them in one
place: total quantity, holder count, first/last dates, search, sort, and a
"leave as is" action that hides a group.
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.htmx import render_modal_or_page
from accounts.permissions import club_admin_required

from ..grouping import OPEN, group_by_name_key
from ..models import PlayerItem

SORT_FIELDS = {
    "name": "display_name",
    "quantity": "total_quantity",
    "holders": "holder_count",
    "first": "first_date",
    "last": "last_date",
}


def _next_dir(sort, direction, field):
    """Return the sort direction to use for the given column."""
    if sort == field and direction == "asc":
        return "desc"
    return "asc"


@club_admin_required
def review(request, club_slug):
    """List player-item groups that still need review, with search and sort."""
    club = request.club
    qs = PlayerItem.objects.for_club(club).select_related("character")
    groups = group_by_name_key(qs)
    # Only groups that still have open items need review; "left as is" groups
    # are hidden from this page.
    groups = [g for g in groups if g["open_count"] > 0]

    q = (request.GET.get("q") or "").strip()
    if q:
        q_lower = q.lower()
        groups = [g for g in groups if q_lower in g["display_name"].lower()]

    sort = request.GET.get("sort", "name")
    direction = request.GET.get("dir", "asc")
    field = SORT_FIELDS.get(sort, "display_name")
    groups.sort(key=lambda g: g[field], reverse=(direction == "desc"))

    ctx = {
        "club": club,
        "groups": groups,
        "q": q,
        "sort": sort,
        "direction": direction,
        "next_dir": {f: _next_dir(sort, direction, f) for f in SORT_FIELDS},
        "is_admin": True,
    }
    return render(request, "player_items/review.html", ctx)


@club_admin_required
def leave_as_is_confirm(request, club_slug):
    """HTMX modal: confirm leaving a group as is."""
    club = request.club
    name_key = request.GET.get("name_key", "")
    if not name_key:
        return redirect("player_items:review", club_slug=club.slug)

    # Get display name for the group
    item = PlayerItem.objects.for_club(club).filter(name_key=name_key).first()
    display_name = item.name if item else name_key

    ctx = {
        "club": club,
        "name_key": name_key,
        "display_name": display_name,
        "confirm_url": reverse("player_items:leave_as_is", args=[club.slug]),
        "modal_title": "Leave as is?",
    }
    return render_modal_or_page(
        request,
        "player_items/_leave_as_is_confirm.html",
        "player_items/_leave_as_is_confirm.html",
        ctx,
    )


@club_admin_required
@require_POST
def leave_as_is(request, club_slug):
    """Mark every open item in a name_key group as left_as_is (hide it)."""
    club = request.club
    name_key = request.POST.get("name_key", "")
    if name_key:
        updated = (
            PlayerItem.objects.for_club(club)
            .filter(name_key=name_key, review=OPEN)
            .update(review="left_as_is")
        )
        if updated:
            messages.success(request, "Group left as is.")
    return redirect("player_items:review", club_slug=club.slug)
