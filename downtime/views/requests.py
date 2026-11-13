"""Downtime point requests (D4). Mirrors the map requests queue (M12)."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Case, IntegerField, When
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.apps import is_gm_or_admin
from accounts.permissions import admin_or_gm_required, club_member_required
from accounts.scoping import club_get_object_or_404, club_queryset
from downtime import services
from downtime.forms_requests import PointRequestForm
from downtime.models import DowntimePointRequest
from player_characters.selection import own_characters, selected_character

Status = DowntimePointRequest.Status


@club_member_required
def queue(request, club_slug):
    is_editor = is_gm_or_admin(request)
    qs = club_queryset(request, DowntimePointRequest)
    if not is_editor:
        qs = qs.filter(requested_by=request.membership) if request.membership else qs.none()
    qs = (
        qs.select_related("requested_by__user", "decided_by__user")
        .prefetch_related("characters")
        .annotate(
            open_first=Case(
                When(status=Status.PENDING, then=0), default=1, output_field=IntegerField()
            )
        )
        .order_by("open_first", "-created")
    )
    return render(
        request,
        "downtime/requests/queue.html",
        {"club": request.club, "is_editor": is_editor, "requests": list(qs)},
    )


@club_member_required
def request_new(request, club_slug):
    if request.membership is None:
        raise PermissionDenied
    chars = own_characters(request)
    if request.method == "POST":
        form = PointRequestForm(request.POST, characters_qs=chars)
        if form.is_valid():
            d = form.cleaned_data
            req = DowntimePointRequest.objects.create(
                club=request.club,
                requested_by=request.membership,
                points=d["points"],
                note=d["note"],
            )
            req.characters.set(d["characters"])
            messages.success(request, "Point request sent.")
            return redirect("downtime:requests", club_slug=club_slug)
    else:
        sel = selected_character(request)
        form = PointRequestForm(
            characters_qs=chars, initial={"characters": [sel.pk]} if sel else {}
        )
    return render(
        request,
        "downtime/requests/form.html",
        {"club": request.club, "form": form, "has_characters": chars.exists()},
    )


def _decide(request, club_slug, pk, status):
    req = club_get_object_or_404(request, DowntimePointRequest, pk=pk)
    with transaction.atomic():
        chars = list(req.characters.all())
        if status == Status.APPROVED and not chars:
            messages.error(request, "This request has no characters. Decline it instead.")
            return redirect("downtime:requests", club_slug=club_slug)
        claimed = DowntimePointRequest.objects.filter(pk=pk, status=Status.PENDING).update(
            status=status, decided_by=request.membership, decided_at=timezone.now()
        )
        if not claimed:
            messages.info(request, "This request was already decided.")
            return redirect("downtime:requests", club_slug=club_slug)
        if status == Status.APPROVED:
            try:
                services.award(
                    chars,
                    req.points,
                    note=req.note or "Point request",
                    by=request.user,
                    kind="request",
                    source=f"request:{req.pk}",
                    club=request.club,
                )
            except services.DowntimeError as exc:
                transaction.set_rollback(True)
                messages.error(request, str(exc))
                return redirect("downtime:requests", club_slug=club_slug)
    messages.success(request, f"Request {status}.")
    return redirect("downtime:requests", club_slug=club_slug)


@admin_or_gm_required
@require_POST
def approve(request, club_slug, pk):
    return _decide(request, club_slug, pk, Status.APPROVED)


@admin_or_gm_required
@require_POST
def decline(request, club_slug, pk):
    return _decide(request, club_slug, pk, Status.DECLINED)


requests_urls = [
    path("requests/", queue, name="requests"),
    path("requests/new/", request_new, name="request_new"),
    path("requests/<int:pk>/approve/", approve, name="request_approve"),
    path("requests/<int:pk>/decline/", decline, name="request_decline"),
]
