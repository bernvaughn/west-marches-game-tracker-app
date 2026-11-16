"""Downtime spend views for dashboard: HTMX partial endpoints for wheel modal."""

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import can_view_inventory, club_member_required
from accounts.scoping import club_get_object_or_404
from downtime import services
from downtime.models import DowntimeAction, DowntimeResult
from downtime.views.play import _result_context, _result_response, _back_to_play
from player_characters.selection import selected_character


@club_member_required
def downtime_spend_partial(request, club_slug, action_pk):
    """
    HTMX partial endpoint for downtime spend from dashboard.
    GET: Returns wheel modal for the action.
    POST: Spends points and returns result modal.
    """
    club = request.club
    membership = request.membership
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
            return _result_response(request, result, spin=True)
        return redirect("downtime:result", club_slug=club.slug, pk=result.pk)

    # GET: Return the wheel modal
    # Build wheel context for the action
    entries = list(action.entries.prefetch_related("items__item"))
    if not entries:
        raise Http404("Action has no rewards.")

    from downtime.wheel import wheel_payload
    from ledger import services as ledger_services

    # Create a dummy result for wheel payload
    class DummyResult:
        def __init__(self, action, entries):
            self.action = action
            self.entries = entries
            self.character = character
            self.entry_id = None

        @property
        def entry(self):
            return None

    dummy = DummyResult(action, entries)
    wheel = wheel_payload(dummy)

    ctx = {
        "action": action,
        "character": character,
        "balance": balance,
        "coin_balance": ledger_services.coin_balance(character),
        "wheel": wheel,
    }

    return render_modal_or_page(
        request,
        "downtime/play/_result_modal.html",
        "downtime/play/result.html",
        ctx,
    )