import json
from datetime import date

from django.contrib import messages
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404, club_queryset
from shops.forms.rotations import RotationForm
from shops.models import Rotation, Shop
from shops.services import ordered_shops


def rotation_status(rotation, today):
    if rotation.open_date > today:
        return "upcoming"
    if rotation.close_date is None:
        return "always open"
    if rotation.close_date < today:
        return "closed"
    return "open"


@club_admin_required
def rotation_list(request, club_slug):
    today = timezone.localdate()
    rotations = club_queryset(request, Rotation).prefetch_related(
        Prefetch("shops", queryset=ordered_shops(Shop.objects.all()))
    )
    rows = [(r, rotation_status(r, today)) for r in rotations]
    return render(request, "shops/rotations/list.html", {"rows": rows})


def _date_param(request):
    try:
        return date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return None


def _save_form(request, club_slug, instance, message):
    initial = {}
    if instance.pk is None and (day := _date_param(request)):
        initial["open_date"] = day
    form = RotationForm(request.POST or None, instance=instance, club=request.club, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, message)
        if is_htmx(request):
            trigger = json.dumps({"appModalClose": True, "agendaChanged": True})
            return None, HttpResponse(status=204, headers={"HX-Trigger": trigger})
        return None, redirect("shops:rotation_list", club_slug=club_slug)
    return form, None


def _render_form(request, form, rotation=None):
    return render_modal_or_page(
        request,
        "shops/rotations/_form_modal.html",
        "shops/rotations/form.html",
        {"form": form, "rotation": rotation},
    )


@club_admin_required
def rotation_create(request, club_slug):
    form, response = _save_form(
        request, club_slug, Rotation(club=request.club), "Rotation created."
    )
    return response or _render_form(request, form)


@club_admin_required
def rotation_edit(request, club_slug, rotation_id):
    rotation = club_get_object_or_404(request, Rotation, pk=rotation_id)
    form, response = _save_form(request, club_slug, rotation, "Rotation saved.")
    return response or _render_form(request, form, rotation)


@club_admin_required
@require_POST
def rotation_delete(request, club_slug, rotation_id):
    rotation = club_get_object_or_404(request, Rotation, pk=rotation_id)
    rotation.delete()
    messages.success(request, "Rotation deleted.")
    return redirect("shops:rotation_list", club_slug=club_slug)
