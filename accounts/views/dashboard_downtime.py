"""Downtime spend views for dashboard: HTMX partial endpoints for wheel modal."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.htmx import is_htmx, render_modal_or_page, set_hx_headers
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from downtime import services
from downtime.models import DowntimeAction
from downtime.views.play import _back_to_play, _result_context
from player_characters.selection import selected_character


@club_member_required
def downtime_spend_partial(request, club_slug, action_pk):
    """
    HTMX partial endpoint for downtime spend from dashboard.
    GET (htmx): Returns a confirm modal for the action.
    GET (no htmx): Redirects to the Downtime page.
    POST: Spends points and returns result modal with toast and dashboard refresh trigger.
    """
    club = request.club
    character = selected_character(request)
    if character is None:
        raise Http404("No character selected.")

    action = club_get_object_or_404(request, DowntimeAction, pk=action_pk)

    # Check if action is live
    today = timezone.localdate()
    if not action.is_live_on(today):
        raise Http404("Action not available today.")

    # Check if character can afford this action
    balance = services.balance(character)
    if balance < action.cost:
        raise Http404("Not enough downtime points.")

    if request.method == "POST":
        # Spend the points
        try:
            result = services.spend(character, action, request.user)
        except services.DowntimeError as exc:
            messages.error(request, str(exc))
            return _back_to_play(request)

        if is_htmx(request):
            # Build result context with wheel
            ctx = _result_context(result, spin=True)
            # Add club to context for URL generation in template
            ctx["club"] = club
            response = render_modal_or_page(
                request,
                "accounts/_dashboard_downtime_result_modal.html",
                "downtime/play/result.html",
                ctx,
            )
            # Emit toast with result summary
            entry = result.entry
            if entry:
                toast_msg = entry.label
                if entry.coins:
                    toast_msg += f" + {entry.coins} cp"
                for ei in entry.items.all():
                    toast_msg += f", {ei.quantity}×{ei.item.name}"
            else:
                toast_msg = "No reward this time."
            set_hx_headers(
                response,
                trigger={
                    "toast": {"message": toast_msg, "type": "success"},
                    "downtimeSpent": True,
                },
            )
            return response
        return redirect("downtime:result", club_slug=club.slug, pk=result.pk)

    # Non-HTMX GET: redirect to the downtime play page where the player can spend the point
    if not is_htmx(request):
        return redirect("downtime:play", club_slug=club.slug)

    # HTMX GET: return a confirm modal. The POST above spins the wheel and spends the point.
    entries = list(action.entries.prefetch_related("items__item"))
    if not entries:
        raise Http404("Action has no rewards.")
    rewards = [
        {"entry": e, "percent": p, "items": list(e.items.all())}
        for e, p in services.chances(entries)
    ]
    ctx = {
        "club": club,
        "action": action,
        "character": character,
        "balance": balance,
        "rewards": rewards,
        "spend_url": request.path,
    }
    return render(request, "accounts/_dashboard_downtime_confirm_modal.html", ctx)
