"""Downtime play views: list live actions, spend points, show the result."""

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import can_view_inventory, club_member_required
from accounts.scoping import club_get_object_or_404
from downtime import services
from downtime.models import DowntimeAction, DowntimeResult
from downtime.wheel import wheel_payload
from ledger import services as ledger_services
from player_characters.selection import selected_character


@club_member_required
def play(request, club_slug):
    today = timezone.localdate()
    character = selected_character(request)
    balance = services.balance(character) if character else None
    live = (
        DowntimeAction.objects.for_club(request.club)
        .live_on(today)
        .filter(entries__isnull=False)
        .distinct()
        .prefetch_related("entries__items__item")
    )
    cards = []
    for action in live:
        rewards = [
            {"entry": e, "percent": p, "items": list(e.items.all())}
            for e, p in services.chances(action.entries.all())
        ]
        reason = ""
        if character is None:
            reason = "You have no character."
        elif balance < action.cost:
            reason = "Not enough downtime points."
        cards.append({"action": action, "rewards": rewards, "reason": reason})
    return render(
        request,
        "downtime/play/index.html",
        {"cards": cards, "character": character, "balance": balance},
    )


def _result_context(res):
    entry = res.entry
    items = list(entry.items.select_related("item")) if entry else []
    return {
        "result": res,
        "entry": entry,
        "items": items,
        "wheel": wheel_payload(res),
        "balance": services.balance(res.character),
        "coin_balance": ledger_services.coin_balance(res.character),
    }


def _result_response(request, res):
    return render_modal_or_page(
        request,
        "downtime/play/_result_modal.html",
        "downtime/play/result.html",
        _result_context(res),
    )


def _back_to_play(request):
    url = reverse("downtime:play", args=[request.club.slug])
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return redirect(url)


@club_member_required
@require_POST
def spend(request, club_slug, pk):
    action = club_get_object_or_404(request, DowntimeAction, pk=pk)
    character = selected_character(request)
    if character is None:
        messages.error(request, "You have no character to spend points for.")
        return _back_to_play(request)
    try:
        result = services.spend(character, action, request.user)
    except services.DowntimeError as exc:
        messages.error(request, str(exc))
        return _back_to_play(request)
    if is_htmx(request):
        return _result_response(request, result)
    return redirect("downtime:result", club_slug=request.club.slug, pk=result.pk)


@club_member_required
def result(request, club_slug, pk):
    res = club_get_object_or_404(request, DowntimeResult, pk=pk)
    if not can_view_inventory(request.user, res.character):
        raise Http404
    return _result_response(request, res)


play_urls = [
    path("", play, name="play"),
    path("spend/<int:pk>/", spend, name="spend"),
    path("result/<int:pk>/", result, name="result"),
]
