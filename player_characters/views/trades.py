from django import forms
from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_queryset

from ..models import Trade
from ..trade_forms import ProposeTradeForm, TradeSideForm
from ..trade_services import OPEN, TradeError, propose_trade


@club_member_required
def index(request, club_slug):
    trades = club_queryset(request, Trade).select_related(
        "sender__owner__user", "receiver__owner__user"
    )
    mine = trades.filter(
        Q(sender__owner__user=request.user) | Q(receiver__owner__user=request.user)
    )
    show_all = is_game_master(request.user, request.club) or is_club_admin(
        request.user, request.club
    )
    return render(
        request,
        "player_characters/trades/index.html",
        {
            "open_trades": mine.filter(status__in=OPEN),
            "closed_trades": mine.exclude(status__in=OPEN),
            "show_all": show_all,
            "all_trades": trades if show_all else [],
        },
    )


def _pick(queryset, raw):
    """Return the object for `raw` id from `queryset`, 404 if absent or invalid."""
    try:
        return queryset.get(pk=int(raw))
    except (TypeError, ValueError, queryset.model.DoesNotExist):
        raise Http404("No such character.") from None


@club_member_required
def propose(request, club_slug):
    club = request.club
    form = ProposeTradeForm(request.user, club)
    senders = form.fields["sender"].queryset
    receivers = form.fields["receiver"].queryset
    ctx = {"form": None, "side_form": None, "sender": None, "choices": senders}
    template = "player_characters/trades/propose.html"
    if not senders.exists():
        return render(request, template, ctx)

    source = request.POST if request.method == "POST" else request.GET
    sender = None
    if request.method == "POST":
        sender = _pick(senders, request.POST.get("sender"))
    elif source.get("from"):
        sender = _pick(senders, source.get("from"))
    elif senders.count() == 1:
        sender = senders.first()

    to = None
    if request.method == "GET" and source.get("to"):
        to = _pick(receivers, source.get("to"))
    ctx["to"] = to

    if sender is None:
        return render(request, template, ctx)

    if request.method == "POST":
        form = ProposeTradeForm(request.user, club, data=request.POST)
        side = TradeSideForm(sender, data=request.POST, prefix="offer")
        if form.is_valid() and side.is_valid():
            cd = form.cleaned_data
            try:
                trade = propose_trade(
                    cd["sender"], cd["receiver"], side.lines(), cd["note"], request.user
                )
            except TradeError as e:
                messages.error(request, str(e))
                url = reverse("trades:propose", args=[club.slug])
                return redirect(f"{url}?from={sender.pk}&to={cd['receiver'].pk}")
            messages.success(request, "Trade proposed.")
            return redirect("trades:detail", club.slug, trade.pk)
    else:
        form = ProposeTradeForm(request.user, club, initial={"sender": sender, "receiver": to})
        side = TradeSideForm(sender, prefix="offer")
    form.fields["sender"].widget = forms.HiddenInput()
    ctx.update({"form": form, "side_form": side, "sender": sender})
    return render(request, template, ctx)
