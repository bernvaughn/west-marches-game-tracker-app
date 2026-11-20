from datetime import date

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.htmx import hx_response, is_htmx, render_modal_or_page
from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404, club_queryset
from shops.forms.rotations import CopyStockForm, RotationForm
from shops.models import Rotation, Shop, ShopStock
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
            return None, hx_response(trigger={"appModalClose": True, "agendaChanged": True})
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


def _copy_stock(form, rotation):
    """Copy source stock entries to every target shop.

    Returns the number of stock entries written (created or updated).
    All writes happen in a single transaction.
    """
    source_type = form.cleaned_data["source_type"]
    target_shops = form.cleaned_data["target_shops"]

    if source_type == CopyStockForm.SOURCE_ROTATION:
        source_rotation = form.cleaned_data["source_rotation"]
        source_stocks = ShopStock.objects.filter(
            shop__in=source_rotation.shops.all()
        ).select_related("item")
    else:
        source_shop = form.cleaned_data["source_shop"]
        source_stocks = ShopStock.objects.filter(shop=source_shop).select_related("item")

    count = 0
    with transaction.atomic():
        for target in target_shops:
            for source in source_stocks:
                ShopStock.objects.update_or_create(
                    shop=target,
                    item=source.item,
                    defaults={
                        "quantity": source.quantity,
                        "sell_percent": source.sell_percent,
                        "buy_percent": source.buy_percent,
                    },
                )
                count += 1
    return count


def _copy_result(count):
    """A success message and HTMX trigger for a completed copy."""
    entry = "entry" if count == 1 else "entries"
    message = f"Copied {count} stock {entry}."
    trigger = {
        "appModalClose": True,
        "toast": {"message": message, "type": "success"},
    }
    return message, trigger


@club_admin_required
def rotation_copy_stock(request, club_slug, rotation_id):
    rotation = club_get_object_or_404(request, Rotation, pk=rotation_id)
    if request.method == "POST":
        form = CopyStockForm(request.POST, club=request.club, rotation=rotation)
        if form.is_valid():
            count = _copy_stock(form, rotation)
            message, trigger = _copy_result(count)
            if is_htmx(request):
                return hx_response(trigger=trigger)
            messages.success(request, message)
            return redirect("shops:rotation_list", club_slug=club_slug)
    else:
        form = CopyStockForm(club=request.club, rotation=rotation)
    return render_modal_or_page(
        request,
        "shops/rotations/_copy_stock_modal.html",
        "shops/rotations/_copy_stock_modal_form.html",
        {"form": form, "rotation": rotation},
    )
