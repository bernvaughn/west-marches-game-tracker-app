"""Approval provider for the navbar indicator (U26)."""

from django.urls import reverse

from accounts.apps import is_gm_or_admin

from .models import DowntimePointRequest


def pending_point_requests(request):
    club = getattr(request, "club", None)
    if club is None or not is_gm_or_admin(request):
        return None
    count = (
        DowntimePointRequest.objects.for_club(club)
        .filter(status=DowntimePointRequest.Status.PENDING)
        .count()
    )
    return ("Downtime point requests", count, reverse("downtime:requests", args=[club.slug]))
