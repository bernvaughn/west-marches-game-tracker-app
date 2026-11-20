"""Downtime points views."""

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import path

from accounts.permissions import admin_or_gm_required
from downtime import services
from downtime.forms import PointsForm
from downtime.models import DowntimePointEntry
from player_characters.models import Character


def _preselected(request):
    # Support both ?character= (singular, existing) and ?characters=1,2,3 (comma list, new)
    pks = []
    # Parse singular character param
    for p in request.GET.getlist("character"):
        if p.isdigit():
            pks.append(p)
    # Parse comma-separated characters param
    characters_param = request.GET.get("characters", "")
    if characters_param:
        for token in characters_param.split(","):
            token = token.strip()
            # Accept only ASCII digits (no unicode digits, no negatives, no blanks)
            if token.isascii() and token.isdigit():
                pks.append(token)
    # De-duplicate and cap to avoid huge queries
    unique_pks = list(dict.fromkeys(pks))[:200]
    return list(Character.objects.for_club(request.club).filter(pk__in=unique_pks))


@admin_or_gm_required
def award_points(request, club_slug):
    club = request.club
    preselected = _preselected(request)
    if request.method == "POST":
        form = PointsForm(request.POST, club=club)
        if form.is_valid():
            delta = form.signed_delta()
            try:
                entries = services.award(
                    list(form.cleaned_data["characters"]),
                    delta,
                    form.cleaned_data["note"],
                    form.cleaned_data["date"],
                    by=request.user,
                    kind="award" if delta > 0 else "remove",
                    club=club,
                )
            except services.DowntimeError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    f"{'Gave' if delta > 0 else 'Took'} {abs(delta)} downtime "
                    f"point{'s' if abs(delta) != 1 else ''} "
                    f"for {len(entries)} character{'s' if len(entries) != 1 else ''}.",
                )
                if len(preselected) == 1 and len(entries) == 1:
                    return redirect("characters:detail", club_slug=club.slug, pk=preselected[0].pk)
                return redirect("downtime:points_award", club_slug=club.slug)
    else:
        form = PointsForm(initial={"characters": [c.pk for c in preselected]}, club=club)
    totals = dict(
        DowntimePointEntry.objects.for_club(club)
        .values_list("character")
        .annotate(total=Sum("delta"))
    )
    if request.method == "POST":
        ticked = set(request.POST.getlist("characters"))
    else:
        ticked = {str(c.pk) for c in preselected}
    rows = [
        {"character": c, "balance": totals.get(c.pk, 0), "checked": str(c.pk) in ticked}
        for c in form.fields["characters"].queryset.select_related("owner__user")
    ]
    return render(
        request,
        "downtime/points_award.html",
        {"form": form, "rows": rows, "club": club},
    )


points_urls = [path("points/", award_points, name="points_award")]
