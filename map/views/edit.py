from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404

from .. import services
from ..forms import EncounterForm, LocationForm, MapEditForm, MapForm
from ..models import Encounter, HexMap, Location


def _tile_url(club_slug, tile):
    return reverse(
        "map:tile",
        kwargs={"club_slug": club_slug, "map_id": tile.map_id, "q": tile.q, "r": tile.r},
    )


def _form_page(request, template, form, title, **extra):
    ctx = {"club": request.club, "form": form, "title": title, **extra}
    return render(request, template, ctx)


@admin_or_gm_required
def map_create(request, club_slug):
    form = MapForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        hex_map = form.save(commit=False)
        hex_map.club = request.club
        hex_map.save()
        return redirect("map:detail", club_slug=club_slug, map_id=hex_map.pk)
    return _form_page(request, "map/edit/map_form.html", form, "New map")


@admin_or_gm_required
def map_edit(request, club_slug, map_id):
    hex_map = club_get_object_or_404(request, HexMap, pk=map_id)
    form = MapEditForm(request.POST or None, instance=hex_map)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("map:detail", club_slug=club_slug, map_id=hex_map.pk)
    return _form_page(
        request, "map/edit/map_form.html", form, "Rename or archive map", hex_map=hex_map
    )


@admin_or_gm_required
def location_create(request, club_slug, map_id, q, r):
    hex_map = club_get_object_or_404(request, HexMap, pk=map_id)
    form = LocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        location = form.save(commit=False)
        location.tile = services.ensure_tile(hex_map, q, r)
        location.save()
        return redirect(_tile_url(club_slug, location.tile))
    back = reverse(
        "map:tile", kwargs={"club_slug": club_slug, "map_id": hex_map.pk, "q": q, "r": r}
    )
    return _form_page(
        request, "map/edit/location_form.html", form, f"Add a location at ({q}, {r})", back=back
    )


@admin_or_gm_required
def location_edit(request, club_slug, pk):
    location = club_get_object_or_404(request, Location, pk=pk)
    form = LocationForm(request.POST or None, instance=location)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_tile_url(club_slug, location.tile))
    return _form_page(
        request,
        "map/edit/location_form.html",
        form,
        "Edit location",
        back=_tile_url(club_slug, location.tile),
    )


@admin_or_gm_required
def location_delete(request, club_slug, pk):
    location = club_get_object_or_404(request, Location, pk=pk)
    tile = location.tile
    if request.method == "POST":
        location.delete()
        services.prune_tile(tile)
        return redirect(_tile_url(club_slug, tile))
    return render(
        request,
        "map/edit/confirm_delete.html",
        {
            "club": request.club,
            "object_name": f"location {location.name}",
            "back": _tile_url(club_slug, tile),
        },
    )


@admin_or_gm_required
def encounter_create(request, club_slug, pk):
    location = club_get_object_or_404(request, Location, pk=pk)
    form = EncounterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        encounter = form.save(commit=False)
        encounter.location = location
        encounter.save()
        return redirect(_tile_url(club_slug, location.tile))
    return _form_page(
        request,
        "map/edit/encounter_form.html",
        form,
        f"Add an encounter at {location.name}",
        back=_tile_url(club_slug, location.tile),
    )


@admin_or_gm_required
def encounter_edit(request, club_slug, pk):
    encounter = club_get_object_or_404(request, Encounter, pk=pk)
    tile = encounter.location.tile
    form = EncounterForm(request.POST or None, instance=encounter)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_tile_url(club_slug, tile))
    return _form_page(
        request,
        "map/edit/encounter_form.html",
        form,
        "Edit encounter",
        back=_tile_url(club_slug, tile),
    )


@admin_or_gm_required
def encounter_delete(request, club_slug, pk):
    encounter = club_get_object_or_404(request, Encounter, pk=pk)
    tile = encounter.location.tile
    if request.method == "POST":
        encounter.delete()
        return redirect(_tile_url(club_slug, tile))
    return render(
        request,
        "map/edit/confirm_delete.html",
        {"club": request.club, "object_name": "this encounter", "back": _tile_url(club_slug, tile)},
    )
