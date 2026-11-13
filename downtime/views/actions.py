"""Downtime actions: club admin pages."""

from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone

from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404
from downtime.forms import DowntimeActionForm, EntryFormSet
from downtime.models import DowntimeAction


@club_admin_required
def actions(request, club_slug):
    today = timezone.localdate()
    rows = [
        {"action": a, "status": a.status_on(today), "count": a.entry_count}
        for a in DowntimeAction.objects.for_club(request.club).annotate(
            entry_count=Count("entries")
        )
    ]
    return render(request, "downtime/manage/list.html", {"rows": rows})


def _form_view(request, action):
    club = request.club
    instance = action or DowntimeAction(club=club)
    data = request.POST if request.method == "POST" else None
    form = DowntimeActionForm(data, instance=instance, club=club)
    entries = EntryFormSet(data, instance=instance, prefix="entries", club=club)
    if request.method == "POST":
        valid = [form.is_valid(), entries.is_valid()]
        if all(valid):
            with transaction.atomic():
                saved = form.save()
                entries.instance = saved
                entries.save()
            messages.success(request, f"Saved downtime action {saved.name}.")
            return redirect("downtime:actions", club_slug=club.slug)
    entries.live_chances()
    return render(
        request,
        "downtime/manage/form.html",
        {"form": form, "entries": entries, "action": action},
    )


@club_admin_required
def action_new(request, club_slug):
    return _form_view(request, None)


@club_admin_required
def action_edit(request, club_slug, pk):
    return _form_view(request, club_get_object_or_404(request, DowntimeAction, pk=pk))


actions_urls = [
    path("manage/", actions, name="actions"),
    path("manage/new/", action_new, name="action_new"),
    path("manage/<int:pk>/", action_edit, name="action_edit"),
]
