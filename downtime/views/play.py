"""Downtime play views: list live actions, spend points, show the result."""

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.mixins import (
    CharacterContextMixin,
    ClubContextMixin,
    ClubScopedMixin,
    PermissionMixin,
)
from accounts.permissions import club_member_required
from downtime import services
from downtime.models import DowntimeAction, DowntimeResult
from downtime.wheel import wheel_payload
from ledger import services as ledger_services


@method_decorator(club_member_required, name="dispatch")
class PlayView(ClubScopedMixin, CharacterContextMixin, ClubContextMixin, View):
    def get(self, request, club_slug):
        today = timezone.localdate()
        character = self.get_selected_character()
        char_ctx = self.get_character_context(character)
        balance = char_ctx["downtime_balance"] if character else None
        live = (
            self.get_club_queryset(DowntimeAction)
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


def _result_context(res, spin=False):
    entry = res.entry
    items = list(entry.items.select_related("item")) if entry else []
    return {
        "result": res,
        "entry": entry,
        "items": items,
        "wheel": wheel_payload(res) if spin else None,
        "balance": services.balance(res.character),
        "coin_balance": ledger_services.coin_balance(res.character),
    }


def _result_response(request, res, spin=False):
    return render_modal_or_page(
        request,
        "downtime/play/_result_modal.html",
        "downtime/play/result.html",
        _result_context(res, spin),
    )


def _back_to_play(request):
    url = reverse("downtime:play", args=[request.club.slug])
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return redirect(url)


@method_decorator(club_member_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class SpendView(ClubScopedMixin, CharacterContextMixin, ClubContextMixin, View):
    def post(self, request, club_slug, pk):
        action = self.get_club_object_or_404(DowntimeAction, pk=pk)
        character = self.get_selected_character()
        if character is None:
            messages.error(request, "You have no character to spend points for.")
            return _back_to_play(request)
        try:
            result = services.spend(character, action, request.user)
        except services.DowntimeError as exc:
            messages.error(request, str(exc))
            return _back_to_play(request)
        if is_htmx(request):
            return _result_response(request, result, spin=True)
        return redirect("downtime:result", club_slug=self.club.slug, pk=result.pk)


@method_decorator(club_member_required, name="dispatch")
class ResultView(ClubScopedMixin, PermissionMixin, View):
    def get(self, request, club_slug, pk):
        res = self.get_club_object_or_404(DowntimeResult, pk=pk)
        if not self.can_view_inventory(request.user, res.character):
            raise Http404
        return _result_response(request, res)


play_urls = [
    path("", PlayView.as_view(), name="play"),
    path("spend/<int:pk>/", SpendView.as_view(), name="spend"),
    path("result/<int:pk>/", ResultView.as_view(), name="result"),
]