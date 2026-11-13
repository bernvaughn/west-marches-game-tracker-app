import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import (
    club_admin_required,
    club_member_required,
    is_club_admin,
    is_game_master,
)
from accounts.scoping import club_get_object_or_404, club_queryset
from ledger.coins import CP_PER_GP, CP_PER_PP, CP_PER_SP

from .availability import available_item_ids
from .availability import where_to_buy as find_where_to_buy
from .forms import ItemForm
from .models import Item
from .rarity import Rarity
from .references import reference_items
from .services import delete_or_retire
from .usage import ownership_counts


@club_member_required
def index(request, club_slug):
    is_admin = is_club_admin(request.user, request.club)
    show_retired = is_admin and request.GET.get("retired") == "1"
    items = club_queryset(request, Item)
    if not show_retired:
        items = items.filter(retired=False)
    items = list(items)
    for_sale = available_item_ids(request.club, timezone.localdate())
    show_counts = is_admin or is_game_master(request.user, request.club)
    counts = ownership_counts(request.club) if show_counts else {}
    for i in items:
        i.for_sale = i.pk in for_sale
        own = counts.get(i.pk)
        i.owner_count = own.characters if own else 0
        i.held_total = own.held if own else 0
    return render(
        request,
        "items/index.html",
        {
            "items": items,
            "is_admin": is_admin,
            "show_retired": show_retired,
            "show_counts": show_counts,
        },
    )


@club_member_required
def where_to_buy(request, club_slug, pk):
    item = club_get_object_or_404(request, Item, pk=pk)
    if item.retired and not is_club_admin(request.user, request.club):
        raise Http404
    offers = find_where_to_buy(request.club, item, timezone.localdate(), request.user)
    return render_modal_or_page(
        request,
        "items/_where_to_buy_modal.html",
        "items/where_to_buy.html",
        {"item": item, "offers": offers},
    )


@club_member_required
def detail(request, club_slug, pk):
    item = club_get_object_or_404(request, Item, pk=pk)
    is_admin = is_club_admin(request.user, request.club)
    if item.retired and not is_admin:
        raise Http404
    return render(request, "items/detail.html", {"item": item, "is_admin": is_admin})


def _form_view(request, instance):
    form = ItemForm(request.POST or None, instance=instance, club=request.club)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        messages.success(request, f"Saved {item.name}.")
        return redirect("items:detail", club_slug=request.club.slug, pk=item.pk)
    return render(request, "items/form.html", {"form": form, "item": instance})


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return None


def _with_item(target, pk):
    parts = urlsplit(target)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "item"] + [("item", str(pk))]
    return urlunsplit(("", "", parts.path, urlencode(query), parts.fragment))


def _int(raw):
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


@club_admin_required
def references(request, club_slug):
    g = request.GET
    value_cp = (
        _int(g.get("value_pp")) * CP_PER_PP
        + _int(g.get("value_gp")) * CP_PER_GP
        + _int(g.get("value_sp")) * CP_PER_SP
        + _int(g.get("value_cp"))
    )
    band = g.get("rarity", "")
    if band not in Rarity.values:
        band = ""
    items = reference_items(
        request.club,
        band,
        value_cp,
        g.get("ref_q", ""),
        exclude_pk=_int(g.get("exclude")) or None,
    )
    return render(request, "items/_references.html", {"items": items})


@club_admin_required
def create(request, club_slug):
    next_url = _safe_next(request)
    form = ItemForm(request.POST or None, club=request.club)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        if is_htmx(request):
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps(
                {"appModalClose": True, "itemCreated": {"id": item.pk, "name": item.name}}
            )
            return response
        messages.success(request, f"Saved {item.name}.")
        if next_url:
            return redirect(_with_item(next_url, item.pk))
        return redirect("items:detail", club_slug=request.club.slug, pk=item.pk)
    return render_modal_or_page(
        request,
        "items/_form_modal.html",
        "items/form.html",
        {"form": form, "item": None, "next_url": next_url},
    )


@club_admin_required
def edit(request, club_slug, pk):
    return _form_view(request, club_get_object_or_404(request, Item, pk=pk))


def _set_retired(request, pk, value, text):
    item = club_get_object_or_404(request, Item, pk=pk)
    item.retired = value
    item.save(update_fields=["retired"])
    messages.success(request, f"{item.name} {text}.")
    return redirect("items:detail", club_slug=request.club.slug, pk=item.pk)


@club_admin_required
@require_POST
def retire(request, club_slug, pk):
    return _set_retired(request, pk, True, "retired")


@club_admin_required
@require_POST
def restore(request, club_slug, pk):
    return _set_retired(request, pk, False, "restored")


@club_admin_required
@require_POST
def delete(request, club_slug, pk):
    item = club_get_object_or_404(request, Item, pk=pk)
    name = item.name
    if delete_or_retire(item):
        messages.success(request, f"Deleted {name}.")
        return redirect("items:index", club_slug=request.club.slug)
    messages.warning(request, f"{name} is in use, so it was retired instead.")
    return redirect("items:detail", club_slug=request.club.slug, pk=pk)
