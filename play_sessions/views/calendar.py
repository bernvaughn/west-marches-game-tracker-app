"""Calendar views: the month grid page, the feed reset, and the public .ics feed."""

import calendar as cal_module
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from accounts.permissions import club_admin_required, club_member_required

from .. import core
from ..feed import build_ics, get_or_create_token, reset_token
from ..models import SessionSettings
from . import calendar as calendar_helpers


@club_member_required
def calendar_page(request, club_slug):
    """The session calendar page: month grid (wide) or upcoming list (phones)."""
    club = request.club
    today = timezone.localdate()
    year, month = calendar_helpers.parse_month(request.GET.get("month"), today)
    grid = calendar_helpers.month_grid(club, year, month, today)
    upcoming = calendar_helpers.upcoming_list(club, year, month, today)
    token = get_or_create_token(club)  # creates the token on first use
    feed_url = request.build_absolute_uri(
        reverse("play_sessions_public:feed", args=[token])
    )
    webcal_url = "webcal://" + feed_url.split("://", 1)[1]
    context = {
        "club": club,
        "grid": grid,
        "upcoming": upcoming,
        "today": today,
        "year": year,
        "month": month,
        "zone_name": core.club_zone(club).key,
        "can_manage": core.can_manage_sessions(request.user, club),
        "feed_url": feed_url,
        "webcal_url": webcal_url,
        "month_name": cal_module.month_name[month],
    }
    return render(request, "play_sessions/calendar.html", context)


@club_admin_required
@require_POST
def feed_reset(request, club_slug):
    """Reset the club's feed token (admin only). Invalidates the old public link."""
    club = request.club
    reset_token(club)
    messages.success(request, "Feed token reset. The old public calendar link no longer works.")
    return redirect("play_sessions:calendar", club_slug=club.slug)


@require_safe
def public_feed(request, token):
    """Public read-only .ics feed. No login, no club_slug; the token identifies the club.

    Wrong or empty token: 404.
    """
    settings = (
        SessionSettings.objects.filter(feed_token=token)
        .exclude(feed_token="")
        .select_related("club")
        .first()
    )
    if settings is None:
        raise Http404("No such feed token")
    club = settings.club
    ics = build_ics(club, timezone.now())
    return HttpResponse(
        ics,
        content_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, max-age=300"},
    )
