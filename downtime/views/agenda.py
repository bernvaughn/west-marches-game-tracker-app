"""Downtime agenda views (U72): one month view of rotations, quests and downtime actions."""

import calendar
import json
from dataclasses import dataclass, field
from datetime import date, timedelta

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import NoReverseMatch, path, reverse
from django.utils import timezone

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404
from downtime.models import DowntimeAction
from quests.models import Quest
from shops.models import Rotation

CHANGED_TRIGGER = json.dumps({"appModalClose": True, "agendaChanged": True})
DATE_FORMAT = "%Y-%m-%d"


@dataclass
class AgendaItem:
    kind: str  # rotation | quest | action
    label: str
    start: date | None
    end: date | None
    edit_url: str
    extra_url: str | None = None
    # Filled in by month_weeks for each week segment.
    col_start: int = 0
    span: int = 1
    lane: int = 0
    continues_left: bool = False
    continues_right: bool = False
    pk: int | None = field(default=None, repr=False)

    @property
    def range_text(self):
        if self.start and self.end:
            return f"{self.start:%d %b %Y} - {self.end:%d %b %Y}"
        if self.start:
            return f"from {self.start:%d %b %Y}"
        if self.end:
            return f"until {self.end:%d %b %Y}"
        return "always"


def parse_month(value, today=None):
    """Return the first day of the month in `value` (YYYY-MM); fall back to this month."""
    today = today or timezone.localdate()
    try:
        year, month = (int(p) for p in value.split("-"))
        return date(year, month, 1)
    except (AttributeError, ValueError, TypeError):
        return today.replace(day=1)


def _shift_month(first, delta):
    index = first.year * 12 + first.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


def _safe_month_from(value):
    return (value or timezone.localdate()).strftime("%Y-%m")


def _date_param(request):
    try:
        return date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return None


def _overlap(field_start, field_end, first, last):
    return Q(**{f"{field_start}__isnull": True}) | Q(**{f"{field_start}__lte": last}), Q(
        **{f"{field_end}__isnull": True}
    ) | Q(**{f"{field_end}__gte": first})


def _full_edit_url(club, action):
    try:
        return reverse("downtime:action_edit", args=[club.slug, action.pk])
    except NoReverseMatch:
        return None


def collect_items(club, first, last):
    """Items of this club overlapping [first, last]; a null start or end means open-ended."""
    slug = club.slug
    items = []
    s, e = _overlap("open_date", "close_date", first, last)
    for r in Rotation.objects.for_club(club).filter(s, e):
        url = reverse("shops:rotation_edit", args=[slug, r.pk])
        items.append(AgendaItem("rotation", r.name, r.open_date, r.close_date, url, pk=r.pk))
    s, e = _overlap("start_date", "end_date", first, last)
    for q in Quest.objects.for_club(club).filter(s, e):
        url = reverse("quests:edit", args=[slug, q.pk])
        items.append(AgendaItem("quest", q.name, q.start_date, q.end_date, url, pk=q.pk))
    for a in DowntimeAction.objects.for_club(club).filter(s, e):
        url = reverse("downtime:agenda_action_edit", args=[slug, a.pk])
        items.append(
            AgendaItem(
                "action", a.name, a.start_date, a.end_date, url, _full_edit_url(club, a), pk=a.pk
            )
        )
    items.sort(key=lambda i: (i.start or date.min, i.label.lower()))
    return items


def month_weeks(year, month, items):
    """Weeks (Monday first) of the month. Each week has days and lane-packed bar segments."""
    weeks = []
    for days in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        first, last = days[0], days[-1]
        segments = []
        for item in items:
            if (item.start and item.start > last) or (item.end and item.end < first):
                continue
            seg_start = max(item.start, first) if item.start else first
            seg_end = min(item.end, last) if item.end else last
            seg = AgendaItem(
                item.kind,
                item.label,
                item.start,
                item.end,
                item.edit_url,
                item.extra_url,
                col_start=(seg_start - first).days + 1,
                span=(seg_end - seg_start).days + 1,
                continues_left=bool(item.start is None or item.start < first),
                continues_right=bool(item.end is None or item.end > last),
                pk=item.pk,
            )
            segments.append(seg)
        lane_ends = []  # last occupied column per lane
        for seg in sorted(segments, key=lambda s: (s.col_start, -s.span)):
            for lane, end_col in enumerate(lane_ends):
                if end_col < seg.col_start:
                    seg.lane = lane
                    lane_ends[lane] = seg.col_start + seg.span - 1
                    break
            else:
                seg.lane = len(lane_ends)
                lane_ends.append(seg.col_start + seg.span - 1)
        weeks.append(
            {
                "days": [{"date": d, "in_month": d.month == month} for d in days],
                "bars": segments,
                "lane_count": len(lane_ends),
            }
        )
    return weeks


class AgendaActionForm(forms.ModelForm):
    class Meta:
        model = DowntimeAction
        fields = ["name", "description", "cost", "start_date", "end_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}, format=DATE_FORMAT),
            "end_date": forms.DateInput(attrs={"type": "date"}, format=DATE_FORMAT),
        }

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "The end date must not be before the start date.")
        return data


@club_admin_required
def agenda(request, club_slug):
    first = parse_month(request.GET.get("month"))
    last = _shift_month(first, 1) - timedelta(days=1)
    items = collect_items(request.club, first, last)
    ctx = {
        "month": first,
        "prev_month": _shift_month(first, -1).strftime("%Y-%m"),
        "next_month": _shift_month(first, 1).strftime("%Y-%m"),
        "weeks": month_weeks(first.year, first.month, items),
        "items": items,
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "today": timezone.localdate(),
    }
    return render_modal_or_page(
        request, "downtime/agenda/_body.html", "downtime/agenda/index.html", ctx
    )


@club_admin_required
def agenda_add(request, club_slug):
    day = _date_param(request)
    ctx = {"date_query": f"?date={day.isoformat()}" if day else "", "day": day}
    return render_modal_or_page(
        request, "downtime/agenda/_add_modal.html", "downtime/agenda/add.html", ctx
    )


def _action_form(request, instance):
    initial = {}
    if instance.pk is None and (day := _date_param(request)):
        initial["start_date"] = day
    form = AgendaActionForm(request.POST or None, instance=instance, initial=initial)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Saved downtime action {saved.name}.")
        if is_htmx(request):
            return None, HttpResponse(status=204, headers={"HX-Trigger": CHANGED_TRIGGER})
        url = reverse("downtime:agenda", args=[request.club.slug])
        month = _safe_month_from(saved.start_date or saved.end_date)
        return None, redirect(f"{url}?month={month}")
    return form, None


def _render_action_form(request, instance):
    form, response = _action_form(request, instance)
    if response:
        return response
    ctx = {
        "form": form,
        "action": instance if instance.pk else None,
        "extra_url": _full_edit_url(request.club, instance) if instance.pk else None,
    }
    return render_modal_or_page(
        request,
        "downtime/agenda/_action_form_modal.html",
        "downtime/agenda/action_form.html",
        ctx,
    )


@club_admin_required
def agenda_action_create(request, club_slug):
    return _render_action_form(request, DowntimeAction(club=request.club))


@club_admin_required
def agenda_action_edit(request, club_slug, pk):
    action = club_get_object_or_404(request, DowntimeAction, pk=pk)
    return _render_action_form(request, action)


agenda_urls = [
    path("agenda/", agenda, name="agenda"),
    path("agenda/add/", agenda_add, name="agenda_add"),
    path("agenda/actions/new/", agenda_action_create, name="agenda_action_create"),
    path("agenda/actions/<int:pk>/", agenda_action_edit, name="agenda_action_edit"),
]
