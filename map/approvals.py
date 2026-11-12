"""Approval provider for the navbar indicator (U26)."""

from django.urls import reverse

from .models import MapRequest
from .visibility import is_map_editor


def open_map_requests(request):
    club = getattr(request, "club", None)
    if club is None or not is_map_editor(request.user, club):
        return None
    count = MapRequest.objects.for_club(club).filter(status=MapRequest.Status.REQUESTED).count()
    return ("Map requests", count, reverse("map:requests", args=[club.slug]))
