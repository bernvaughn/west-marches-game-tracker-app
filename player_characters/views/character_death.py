"""Stub views for character death actions (C1). Later stories replace the bodies."""

from django.http import Http404

from accounts.permissions import club_member_required


@club_member_required
def death(request, club_slug, pk):
    raise Http404


@club_member_required
def death_undo(request, club_slug, pk):
    raise Http404
