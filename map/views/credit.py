from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404, club_queryset
from player_characters.models import Character

from .. import services
from ..forms_credit import PickForm
from ..models import HexMap, Location, LocationCredit, TileVisit
from ..visibility import pick_characters


def _picked(request):
    return list(pick_characters(request, request.POST.getlist("characters"), allow_any=True))


def _bound_form(request, chars):
    form = PickForm(request.POST)
    ok = form.is_valid()
    if ok and not chars:
        form.add_error(None, "Pick at least one character.")
        ok = False
    return form, ok


@admin_or_gm_required
@require_http_methods(["GET", "POST"])
def visits(request, club_slug, map_id, q, r):
    hex_map = club_get_object_or_404(request, HexMap, pk=map_id)
    form = PickForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "remove":
            visit = club_get_object_or_404(
                request, TileVisit, pk=_int(request.POST.get("visit_id")), map=hex_map, q=q, r=r
            )
            visit.delete()
            messages.success(request, "Visit removed.")
            return redirect(request.path)
        chars = _picked(request)
        form, ok = _bound_form(request, chars)
        if action == "add" and ok:
            created = services.record_visits(hex_map, q, r, chars, form.cleaned_data["date"])
            messages.success(request, f"Recorded {len(created)} new visit(s).")
            return redirect(request.path)
    visit_list = (
        TileVisit.objects.for_club(request.club)
        .filter(map=hex_map, q=q, r=r)
        .select_related("character")
        .order_by("character__name")
    )
    return render(
        request,
        "map/credit/visits.html",
        {
            "club": request.club,
            "hex_map": hex_map,
            "q": q,
            "r": r,
            "visits": visit_list,
            "characters": club_queryset(request, Character).order_by("name"),
            "form": form,
        },
    )


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise Http404 from None


@admin_or_gm_required
@require_http_methods(["GET", "POST"])
def credit(request, club_slug, pk, kind):
    if kind not in LocationCredit.Kind.values:
        raise Http404
    location = club_get_object_or_404(request, Location, pk=pk)
    form = PickForm()
    if request.method == "POST":
        action = request.POST.get("action")
        chars = _picked(request)
        if action == "remove":
            if chars:
                services.remove_from_credit(location, kind, chars)
                messages.success(request, f"Removed {len(chars)} character(s).")
            else:
                messages.error(request, "Pick at least one character to remove.")
            return redirect(request.path)
        form, ok = _bound_form(request, chars)
        if action == "add" and ok:
            services.add_to_credit(location, kind, chars, form.cleaned_data["date"])
            messages.success(request, f"Added {len(chars)} character(s).")
            return redirect(request.path)
    entry = LocationCredit.objects.filter(location=location, kind=kind).first()
    credited = list(entry.characters.order_by("name")) if entry else []
    credited_ids = {c.pk for c in credited}
    available = [
        c for c in club_queryset(request, Character).order_by("name") if c.pk not in credited_ids
    ]
    tile = location.tile
    return render(
        request,
        "map/credit/credit.html",
        {
            "club": request.club,
            "hex_map": tile.map,
            "q": tile.q,
            "r": tile.r,
            "location": location,
            "kind": kind,
            "other_kind": "explored" if kind == "discovered" else "discovered",
            "credit": entry,
            "credited": credited,
            "available": available,
            "form": form,
        },
    )
