"""Approval providers for the navbar indicator (U26)."""

from django.urls import reverse

from accounts.permissions import is_club_admin, is_game_master

from .models import ProposedBatch, ProposedItem


def pending_batches(request):
    club = getattr(request, "club", None)
    if club is None or not is_game_master(request.user, club):
        return None
    count = ProposedBatch.objects.for_club(club).filter(status=ProposedBatch.Status.PENDING).count()
    return ("Agent batches", count, reverse("agent_access:batches", args=[club.slug]))


def pending_proposed_items(request):
    club = getattr(request, "club", None)
    if club is None:
        return None
    if not (is_game_master(request.user, club) or is_club_admin(request.user, club)):
        return None
    count = ProposedItem.objects.for_club(club).filter(status=ProposedItem.Status.PENDING).count()
    return ("Proposed items", count, reverse("agent_access:proposed_items", args=[club.slug]))
