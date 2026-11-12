from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Case, IntegerField, When
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import admin_or_gm_required, club_member_required
from accounts.scoping import club_get_object_or_404, club_queryset
from player_characters.selection import selected_character

from .. import services
from ..forms_requests import CreditRequestForm, VisitRequestForm
from ..models import HexMap, Location, LocationCredit, MapRequest, Tile
from ..visibility import found_location_ids, is_map_editor, own_characters, visible_positions

LOCATION_KINDS = {
    LocationCredit.Kind.DISCOVERED,
    LocationCredit.Kind.EXPLORED,
    MapRequest.Kind.FOUND,
}


def _get_map(request, map_id, is_editor):
    hex_map = club_get_object_or_404(request, HexMap, pk=map_id)
    if hex_map.archived and not is_editor:
        raise Http404
    return hex_map


def _get_visible_location(request, pk, is_editor):
    location = club_get_object_or_404(request, Location, pk=pk)
    hex_map = location.tile.map
    if hex_map.archived and not is_editor:
        raise Http404
    if not is_editor:
        visible = visible_positions(hex_map, own_characters(request))
        if (location.tile.q, location.tile.r) not in visible:
            raise Http404
    discovered = LocationCredit.objects.filter(
        location=location, kind=LocationCredit.Kind.DISCOVERED, characters__isnull=False
    )
    if not discovered.exists():
        raise Http404
    return location


def _need_membership(request):
    if request.membership is None:
        raise PermissionDenied


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _location_label(location, characters, is_editor, secret=False):
    """Name for a request. Players see it only when every picked character found it."""
    if location is None:
        return "Location deleted"
    if is_editor:
        return location.name
    if secret or not characters:
        return "Unknown location"
    if all(location.pk in found_location_ids([c]) for c in characters):
        return location.name
    return "Unknown location"


def _default_character(request):
    sel = selected_character(request)
    return {"characters": [sel.pk]} if sel else {}


@club_member_required
def visit_new(request, club_slug, map_id):
    is_editor = is_map_editor(request.user, request.club)
    hex_map = _get_map(request, map_id, is_editor)
    _need_membership(request)
    chars = own_characters(request)
    if request.method == "POST":
        form = VisitRequestForm(request.POST, characters_qs=chars)
        if form.is_valid():
            d = form.cleaned_data
            tile = Tile.objects.filter(map=hex_map, q=d["q"], r=d["r"]).first()
            req = MapRequest.objects.create(
                club=request.club,
                kind=MapRequest.Kind.VISIT,
                map=hex_map,
                q=d["q"],
                r=d["r"],
                tile=tile,
                date=d["date"],
                note=d["note"],
                requested_by=request.membership,
            )
            req.characters.set(d["characters"])
            messages.success(request, "Visit request sent.")
            return redirect("map:requests", club_slug=club_slug)
    else:
        form = VisitRequestForm(
            characters_qs=chars,
            initial={
                "q": _int(request.GET.get("q")),
                "r": _int(request.GET.get("r")),
                **_default_character(request),
            },
        )
    return render(
        request,
        "map/requests/form.html",
        {
            "club": request.club,
            "form": form,
            "title": "Request a visit",
            "hex_map": hex_map,
            "subtitle": f"Map: {hex_map.name}. Tile: {form['q'].value()}, {form['r'].value()}",
            "has_characters": chars.exists(),
        },
    )


@club_member_required
def credit_new(request, club_slug, location_id, kind):
    if kind not in LOCATION_KINDS:
        raise Http404
    is_editor = is_map_editor(request.user, request.club)
    location = _get_visible_location(request, location_id, is_editor)
    _need_membership(request)
    chars = own_characters(request)
    if request.method == "POST":
        form = CreditRequestForm(request.POST, characters_qs=chars)
        if form.is_valid():
            d = form.cleaned_data
            tile = location.tile
            req = MapRequest.objects.create(
                club=request.club,
                kind=kind,
                location=location,
                tile=tile,
                map=tile.map,
                q=tile.q,
                r=tile.r,
                date=d["date"],
                note=d["note"],
                requested_by=request.membership,
            )
            req.characters.set(d["characters"])
            messages.success(request, "Request sent.")
            return redirect("map:requests", club_slug=club_slug)
    else:
        form = CreditRequestForm(characters_qs=chars, initial=_default_character(request))
    if request.method == "POST":
        picked_ids = {_int(v) for v in request.POST.getlist("characters")}
    else:
        picked_ids = set(_default_character(request).get("characters", []))
    picked = [c for c in chars if c.pk in picked_ids]
    label = _location_label(location, picked, is_editor, secret=(kind == "found"))
    tile = location.tile
    return render(
        request,
        "map/requests/form.html",
        {
            "club": request.club,
            "form": form,
            "title": "Request a found mark" if kind == "found" else f"Request {kind} credit",
            "hex_map": location.tile.map,
            "location_label": label,
            "subtitle": f"Map: {tile.map.name}. Tile: {tile.q}, {tile.r}. Location: {label}",
            "has_characters": chars.exists(),
        },
    )


def _can_approve(req, characters):
    if not characters:
        return False
    if req.kind == MapRequest.Kind.VISIT:
        return req.map_id is not None and req.q is not None and req.r is not None
    return req.location_id is not None


@club_member_required
def queue(request, club_slug):
    is_editor = is_map_editor(request.user, request.club)
    qs = club_queryset(request, MapRequest)
    if not is_editor:
        qs = qs.filter(requested_by=request.membership) if request.membership else qs.none()
    qs = (
        qs.select_related("map", "location__tile", "tile", "requested_by__user", "decided_by__user")
        .prefetch_related("characters")
        .annotate(
            open_first=Case(
                When(status=MapRequest.Status.REQUESTED, then=0),
                default=1,
                output_field=IntegerField(),
            )
        )
        .order_by("open_first", "-created")
    )
    requests_list = list(qs)
    for req in requests_list:
        picked = list(req.characters.all())
        req.location_label = _location_label(req.location, picked, is_editor)
        src = req.tile or (req.location.tile if req.location else None)
        req.tile_q = req.q if req.q is not None else (src.q if src else None)
        req.tile_r = req.r if req.q is not None else (src.r if src else None)
        req.can_approve = _can_approve(req, list(req.characters.all()))
    return render(
        request,
        "map/requests/queue.html",
        {"club": request.club, "is_editor": is_editor, "requests": requests_list},
    )


def _decide(request, club_slug, pk, status):
    req = club_get_object_or_404(request, MapRequest, pk=pk)
    with transaction.atomic():
        chars = list(req.characters.all())
        if status == MapRequest.Status.APPROVED and not _can_approve(req, chars):
            messages.error(request, "This request cannot be approved. Decline it instead.")
            return redirect("map:requests", club_slug=club_slug)
        claimed = MapRequest.objects.filter(pk=pk, status=MapRequest.Status.REQUESTED).update(
            status=status, decided_by=request.membership, decided_at=timezone.now()
        )
        if not claimed:
            messages.info(request, "This request was already decided.")
            return redirect("map:requests", club_slug=club_slug)
        if status == MapRequest.Status.APPROVED:
            if req.kind == MapRequest.Kind.VISIT:
                services.record_visits(req.map, req.q, req.r, chars, req.date)
            elif req.kind == MapRequest.Kind.FOUND:
                services.add_found_marks(
                    req.location, chars, req.date, created_by=request.membership
                )
            else:
                services.add_to_credit(req.location, req.kind, chars, req.date)
    messages.success(request, f"Request {status}.")
    return redirect("map:requests", club_slug=club_slug)


@admin_or_gm_required
@require_POST
def approve(request, club_slug, pk):
    return _decide(request, club_slug, pk, MapRequest.Status.APPROVED)


@admin_or_gm_required
@require_POST
def decline(request, club_slug, pk):
    return _decide(request, club_slug, pk, MapRequest.Status.DECLINED)
