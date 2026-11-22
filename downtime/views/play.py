"""Downtime play views: list live actions, spend points, show the result."""

from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from accounts.htmx import htmx_or_redirect, is_htmx, render_modal_or_page, set_hx_headers
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
from player_characters import life

COST_CHOICES = ("1", "2", "3+")
REWARD_CHOICES = ("coins", "items", "mixed")
AVAILABILITY_CHOICES = ("now", "upcoming")


def _live_q(today):
    """Q matching actions available on `date` (open start/end allowed)."""
    return Q(
        Q(start_date__isnull=True) | Q(start_date__lte=today),
        Q(end_date__isnull=True) | Q(end_date__gte=today),
    )


def _reward_type(action):
    """Reward type of an action from its entries: coins, items, or mixed.

    Coins: outcomes can include coins but never items. Items: outcomes can
    include items but never coins. Mixed: outcomes can include both (across
    entries), or neither.
    Entries are expected to be prefetched by the caller.
    """
    can_coins = any(entry.coins > 0 for entry in action.entries.all())
    can_items = any(entry.items.exists() for entry in action.entries.all())
    if can_coins and can_items:
        return "mixed"
    if can_coins:
        return "coins"
    if can_items:
        return "items"
    return "mixed"


@method_decorator(club_member_required, name="dispatch")
class PlayView(ClubScopedMixin, CharacterContextMixin, ClubContextMixin, View):
    def get(self, request, club_slug):
        today = timezone.localdate()
        character = self.get_selected_character()
        char_ctx = self.get_character_context(character)
        balance = char_ctx["downtime_balance"] if character else None

        costs = request.GET.getlist("cost")
        reward_types = request.GET.getlist("reward")
        avails = request.GET.getlist("availability")

        qs = (
            self.get_club_queryset(DowntimeAction)
            .filter(entries__isnull=False)
            .distinct()
            .prefetch_related("entries__items__item")
        )
        if avails:
            cond = Q()
            if "now" in avails:
                cond |= _live_q(today)
            if "upcoming" in avails:
                cond |= Q(start_date__gt=today)
            qs = qs.filter(cond)
        else:
            # No availability chip: keep the current behavior (live actions only).
            qs = qs.live_on(today)

        if costs:
            cond = Q()
            if "1" in costs:
                cond |= Q(cost=1)
            if "2" in costs:
                cond |= Q(cost=2)
            if "3+" in costs:
                cond |= Q(cost__gte=3)
            qs = qs.filter(cond)

        actions = list(qs)
        if reward_types:
            wanted = set(reward_types)
            actions = [a for a in actions if _reward_type(a) in wanted]

        cards = []
        for action in actions:
            rewards = [
                {"entry": e, "percent": p, "items": list(e.items.all())}
                for e, p in services.chances(action.entries.all())
            ]
            reason = ""
            if character is None:
                reason = "You have no character."
            elif life.buy_block_reason(character):
                reason = life.buy_block_reason(character)
            elif balance < action.cost:
                reason = "Not enough downtime points."
            cards.append({"action": action, "rewards": rewards, "reason": reason})
        ctx = {
            "cards": cards,
            "character": character,
            "balance": balance,
            "cost_1": "1" in costs,
            "cost_2": "2" in costs,
            "cost_3plus": "3+" in costs,
            "reward_coins": "coins" in reward_types,
            "reward_items": "items" in reward_types,
            "reward_mixed": "mixed" in reward_types,
            "avail_now": "now" in avails,
            "avail_upcoming": "upcoming" in avails,
            "has_filters": bool(costs or reward_types or avails),
            "is_htmx": is_htmx(request),
        }
        return render_modal_or_page(
            request,
            "downtime/play/_jobs.html",
            "downtime/play/index.html",
            ctx,
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
    return htmx_or_redirect(request, url)


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
            response = _result_response(request, result, spin=True)
            set_hx_headers(response, trigger="downtimeSpent")
            return response
        return redirect("downtime:result", club_slug=self.club.slug, pk=result.pk)


@method_decorator(club_member_required, name="dispatch")
class ResultView(ClubScopedMixin, PermissionMixin, View):
    def get(self, request, club_slug, pk):
        res = self.get_club_object_or_404(DowntimeResult, pk=pk)
        if not self.can_view_inventory(request.user, res.character):
            raise Http404
        return _result_response(request, res)


@method_decorator(club_member_required, name="dispatch")
class ReplayView(ClubScopedMixin, PermissionMixin, View):
    """Re-render the result modal with spin=True so the wheel re-runs the same result."""

    def get(self, request, club_slug, pk):
        res = self.get_club_object_or_404(DowntimeResult, pk=pk)
        if not self.can_view_inventory(request.user, res.character):
            raise Http404
        return _result_response(request, res, spin=True)


play_urls = [
    path("", PlayView.as_view(), name="play"),
    path("spend/<int:pk>/", SpendView.as_view(), name="spend"),
    path("result/<int:pk>/", ResultView.as_view(), name="result"),
    path("result/<int:pk>/replay/", ReplayView.as_view(), name="replay"),
]
