from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render

from accounts.permissions import club_member_required, is_club_admin
from map import xp
from map.models import XPLevel


def _build_form(rows, data=None):
    fields = {}
    for row in rows:
        for kind in ("discover", "explore"):
            fields[f"{kind}_{row.band}"] = forms.IntegerField(
                min_value=0, label=f"{kind} {row.band}"
            )
    return type("XPForm", (forms.Form,), fields)(data)


@club_member_required
def xp_table(request, club_slug):
    club = request.club
    can_edit = is_club_admin(request.user, club)
    rows = xp.xp_table(club)
    form = None
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = _build_form(rows, request.POST)
        if form.is_valid():
            with transaction.atomic():
                for row in XPLevel.objects.filter(club=club):
                    row.discover_xp = form.cleaned_data[f"discover_{row.band}"]
                    row.explore_xp = form.cleaned_data[f"explore_{row.band}"]
                    row.save()
            messages.success(request, "XP table saved.")
            return redirect("map:xp", club.slug)
    elif can_edit:
        form = _build_form(rows)
    lines = []
    for row in rows:
        d = e = None
        if form is not None:
            d, e = form[f"discover_{row.band}"], form[f"explore_{row.band}"]
        lines.append({"row": row, "label": xp.band_label(row.band), "discover": d, "explore": e})
    return render(
        request,
        "map/xp/table.html",
        {"club": club, "lines": lines, "can_edit": can_edit, "form": form},
    )
